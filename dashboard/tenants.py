"""
Multi-tenancy para iConnect — isolamento lógico por organização.

Arquitetura: Row-level tenancy com middleware automático.
Cada tenant (organização) tem seus dados isolados via FK + filtro automático.
"""
import logging
import threading

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('dashboard')

# Thread-local storage para o tenant corrente  
_tenant_context = threading.local()


def get_current_tenant():
    """Retorna o tenant ativo no request atual (ou None)."""
    return getattr(_tenant_context, 'tenant', None)


def set_current_tenant(tenant):
    """Define o tenant ativo para o contexto atual."""
    _tenant_context.tenant = tenant


def clear_current_tenant():
    """Limpa o tenant do contexto."""
    _tenant_context.tenant = None


# ======================== MODELS ========================

class Tenant(models.Model):
    """
    Organização / empresa — unidade de isolamento de dados.
    
    Cada Tenant possui seu slug (subdomínio), limites e configurações.
    """
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]

    name = models.CharField('Nome da Organização', max_length=150)
    slug = models.SlugField('Slug', max_length=80, unique=True, help_text='Identificador único (subdomínio)')
    domain = models.CharField('Domínio personalizado', max_length=255, blank=True, null=True, unique=True)
    logo = models.ImageField('Logo', upload_to='tenants/logos/', blank=True, null=True)
    plan = models.CharField('Plano', max_length=20, choices=PLAN_CHOICES, default='free')

    # Limites por plano
    max_agents = models.PositiveIntegerField('Máx. agentes', default=3)
    max_tickets_month = models.PositiveIntegerField('Máx. tickets/mês', default=100)

    # Configurações visuais
    primary_color = models.CharField('Cor primária', max_length=7, default='#7c3aed')
    secondary_color = models.CharField('Cor secundária', max_length=7, default='#10b981')

    # Status
    is_active = models.BooleanField('Ativo', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Owner
    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='owned_tenants',
        verbose_name='Proprietário',
    )

    class Meta:
        verbose_name = 'Organização'
        verbose_name_plural = 'Organizações'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.slug})'

    @property
    def is_within_agent_limit(self):
        return self.memberships.filter(is_active=True).count() < self.max_agents

    @property
    def tickets_this_month(self):
        from .models import Ticket
        now = timezone.now()
        return Ticket.objects.filter(
            tenant=self,
            criado_em__year=now.year,
            criado_em__month=now.month,
        ).count()

    @property
    def is_within_ticket_limit(self):
        return self.tickets_this_month < self.max_tickets_month


class TenantMembership(models.Model):
    """
    Vínculo entre User e Tenant com papel específico.
    Um user pode pertencer a múltiplos tenants.
    """
    ROLE_CHOICES = [
        ('owner', 'Proprietário'),
        ('admin', 'Administrador'),
        ('supervisor', 'Supervisor'),
        ('agent', 'Agente'),
        ('viewer', 'Visualizador'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_memberships')
    role = models.CharField('Papel', max_length=20, choices=ROLE_CHOICES, default='agent')
    is_active = models.BooleanField('Ativo', default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Membro da Organização'
        verbose_name_plural = 'Membros da Organização'
        unique_together = ['tenant', 'user']
        ordering = ['tenant', '-role']

    def __str__(self):
        return f'{self.user.username} → {self.tenant.slug} ({self.role})'


class TenantInvite(models.Model):
    """Convite para um tenant — permite onboarding por e-mail."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='invites')
    email = models.EmailField('E-mail')
    role = models.CharField('Papel', max_length=20, choices=TenantMembership.ROLE_CHOICES, default='agent')
    token = models.CharField('Token', max_length=64, unique=True)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = 'Convite'
        verbose_name_plural = 'Convites'

    def __str__(self):
        return f'Convite {self.email} → {self.tenant.slug}'

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


# ======================== MIXIN para modelos tenant-aware ========================

class TenantAwareManager(models.Manager):
    """Manager que filtra automaticamente pelo tenant do contexto."""

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant is not None:
            qs = qs.filter(tenant=tenant)
        return qs


class TenantAwareMixin(models.Model):
    """
    Mixin abstrato para qualquer modelo que precise de isolamento por tenant.
    
    Adiciona campo `tenant` FK e usa TenantAwareManager como manager padrão.
    """
    tenant = models.ForeignKey(
        'dashboard.Tenant', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='%(class)s_set',
        verbose_name='Organização',
    )

    # Manager com filtro automático
    tenant_objects = TenantAwareManager()
    # Manager sem filtro (para admin/superuser)
    objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Auto-atribuir tenant se não definido
        if not self.tenant_id:
            current = get_current_tenant()
            if current:
                self.tenant = current
        super().save(*args, **kwargs)


# ======================== MIDDLEWARE ========================

class TenantMiddleware(MiddlewareMixin):
    """
    Detecta o tenant com base no subdomínio ou header X-Tenant-Slug.
    
    Prioridade:
    1. Header X-Tenant-Slug (APIs)
    2. Subdomínio (ex: empresa.iconnect.com.br)
    3. Membership do usuário (fallback)
    """

    def process_request(self, request):
        tenant = None

        # 1. Try header (APIs)
        slug = request.META.get('HTTP_X_TENANT_SLUG')
        if slug:
            tenant = Tenant.objects.filter(slug=slug, is_active=True).first()

        # 2. Try subdomain
        if not tenant:
            host = request.get_host().split(':')[0]  # remove port
            parts = host.split('.')
            if len(parts) >= 3:
                subdomain = parts[0]
                if subdomain not in ('www', 'api', 'admin'):
                    tenant = Tenant.objects.filter(slug=subdomain, is_active=True).first()

        # 3. Try custom domain
        if not tenant:
            host = request.get_host().split(':')[0]
            tenant = Tenant.objects.filter(domain=host, is_active=True).first()

        # 4. Fallback: first tenant of authenticated user
        if not tenant and hasattr(request, 'user') and request.user.is_authenticated:
            membership = TenantMembership.objects.filter(
                user=request.user, is_active=True
            ).select_related('tenant').first()
            if membership:
                tenant = membership.tenant

        set_current_tenant(tenant)
        request.tenant = tenant

    def process_response(self, request, response):
        clear_current_tenant()
        return response


# ======================== CONTEXT PROCESSOR ========================

def tenant_context(request):
    """Disponibiliza tenant no contexto de templates."""
    tenant = getattr(request, 'tenant', None)
    ctx = {
        'current_tenant': tenant,
        'tenant_name': tenant.name if tenant else 'iConnect',
        'tenant_logo': tenant.logo.url if tenant and tenant.logo else None,
        'tenant_primary_color': tenant.primary_color if tenant else '#7c3aed',
        'tenant_secondary_color': tenant.secondary_color if tenant else '#10b981',
    }

    if tenant and hasattr(request, 'user') and request.user.is_authenticated:
        membership = TenantMembership.objects.filter(
            tenant=tenant, user=request.user, is_active=True
        ).first()
        ctx['tenant_role'] = membership.role if membership else None
        ctx['user_tenants'] = Tenant.objects.filter(
            memberships__user=request.user, memberships__is_active=True
        )
    else:
        ctx['tenant_role'] = None
        ctx['user_tenants'] = Tenant.objects.none()

    return ctx


# ======================== VIEWS ========================

import json
import secrets
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET


@login_required
@require_GET
def api_tenant_info(request):
    """GET /api/tenant/ — info do tenant corrente."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Nenhum tenant ativo'}, status=404)

    return JsonResponse({
        'id': tenant.id,
        'name': tenant.name,
        'slug': tenant.slug,
        'plan': tenant.plan,
        'max_agents': tenant.max_agents,
        'max_tickets_month': tenant.max_tickets_month,
        'tickets_this_month': tenant.tickets_this_month,
        'primary_color': tenant.primary_color,
        'is_active': tenant.is_active,
    })


@login_required
@require_GET
def api_tenant_members(request):
    """GET /api/tenant/members/ — membros do tenant."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Nenhum tenant ativo'}, status=404)

    members = TenantMembership.objects.filter(tenant=tenant, is_active=True).select_related('user')
    data = [
        {
            'id': m.id,
            'username': m.user.username,
            'email': m.user.email,
            'full_name': m.user.get_full_name(),
            'role': m.role,
            'joined_at': m.joined_at.isoformat(),
        }
        for m in members
    ]
    return JsonResponse({'members': data})


@login_required
@require_POST
def api_tenant_invite(request):
    """
    POST /api/tenant/invite/
    Body: { "email": "...", "role": "agent" }
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Nenhum tenant ativo'}, status=404)

    # Verificar se user é admin/owner
    membership = TenantMembership.objects.filter(
        tenant=tenant, user=request.user, role__in=['owner', 'admin']
    ).first()
    if not membership:
        return JsonResponse({'error': 'Sem permissão para convidar'}, status=403)

    try:
        data = json.loads(request.body)
        email = data.get('email')
        role = data.get('role', 'agent')

        if not email:
            return JsonResponse({'error': 'E-mail obrigatório'}, status=400)

        invite = TenantInvite.objects.create(
            tenant=tenant,
            email=email,
            role=role,
            token=secrets.token_urlsafe(48),
            invited_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )

        logger.info(f'Convite enviado: {email} → {tenant.slug} ({role})')

        return JsonResponse({
            'success': True,
            'invite_token': invite.token,
            'expires_at': invite.expires_at.isoformat(),
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)


@login_required
@require_POST
def api_switch_tenant(request):
    """
    POST /api/tenant/switch/
    Body: { "tenant_slug": "empresa-x" }
    Alterna o tenant ativo para o usuário.
    """
    try:
        data = json.loads(request.body)
        slug = data.get('tenant_slug')

        if not slug:
            return JsonResponse({'error': 'tenant_slug obrigatório'}, status=400)

        membership = TenantMembership.objects.filter(
            user=request.user, tenant__slug=slug, is_active=True
        ).select_related('tenant').first()

        if not membership:
            return JsonResponse({'error': 'Sem acesso a este tenant'}, status=403)

        # Armazenar na sessão
        request.session['active_tenant_slug'] = slug
        set_current_tenant(membership.tenant)

        return JsonResponse({
            'success': True,
            'tenant': {
                'name': membership.tenant.name,
                'slug': membership.tenant.slug,
                'role': membership.role,
            },
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)


@login_required
@require_GET
def api_user_tenants(request):
    """GET /api/tenants/ — lista todos os tenants do usuário."""
    memberships = TenantMembership.objects.filter(
        user=request.user, is_active=True
    ).select_related('tenant')

    data = [
        {
            'slug': m.tenant.slug,
            'name': m.tenant.name,
            'plan': m.tenant.plan,
            'role': m.role,
            'logo': m.tenant.logo.url if m.tenant.logo else None,
        }
        for m in memberships
    ]

    return JsonResponse({'tenants': data})
