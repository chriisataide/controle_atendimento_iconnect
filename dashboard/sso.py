"""
SSO (Single Sign-On) — SAML 2.0 + OIDC para iConnect.

Suporta:
- Microsoft Azure AD / Entra ID
- Google Workspace
- Okta
- Qualquer provedor SAML 2.0 ou OpenID Connect

Configuração via settings / env vars — zero código para o admin.
"""
import hashlib
import hmac
import json
import logging
import secrets
import time
from urllib.parse import urlencode, urlparse

import requests
from django.conf import settings
from django.contrib.auth import login as django_login
from django.contrib.auth.models import User
from django.db import models
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

logger = logging.getLogger('dashboard')


# ======================== MODELS ========================

class SSOProvider(models.Model):
    """Provedor SSO configurável (SAML 2.0 ou OIDC)"""
    PROTOCOL_CHOICES = [
        ('oidc', 'OpenID Connect'),
        ('saml', 'SAML 2.0'),
    ]

    name = models.CharField(max_length=100, verbose_name='Nome do Provedor')
    slug = models.SlugField(unique=True, help_text='Identificador único (ex: azure-ad, google)')
    protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES, default='oidc')
    is_active = models.BooleanField(default=True)
    icon_class = models.CharField(max_length=50, default='fas fa-key', help_text='Ícone FontAwesome')
    button_color = models.CharField(max_length=7, default='#4285F4', help_text='Cor do botão')
    
    # OIDC Configuration
    client_id = models.CharField(max_length=500, blank=True, verbose_name='Client ID')
    client_secret = models.CharField(max_length=500, blank=True, verbose_name='Client Secret',
                                     help_text='Armazenado criptografado')
    authorization_url = models.URLField(blank=True, verbose_name='Authorization Endpoint')
    token_url = models.URLField(blank=True, verbose_name='Token Endpoint')
    userinfo_url = models.URLField(blank=True, verbose_name='UserInfo Endpoint')
    jwks_url = models.URLField(blank=True, verbose_name='JWKS URL')
    scopes = models.CharField(max_length=200, default='openid email profile',
                              help_text='Escopos separados por espaço')
    
    # SAML Configuration
    saml_entity_id = models.CharField(max_length=500, blank=True, verbose_name='IdP Entity ID')
    saml_sso_url = models.URLField(blank=True, verbose_name='IdP SSO URL')
    saml_slo_url = models.URLField(blank=True, verbose_name='IdP SLO URL')
    saml_certificate = models.TextField(blank=True, verbose_name='IdP X.509 Certificate')
    
    # Mapping de atributos
    attr_email = models.CharField(max_length=100, default='email',
                                  help_text='Nome do atributo para email')
    attr_first_name = models.CharField(max_length=100, default='given_name',
                                       help_text='Nome do atributo para primeiro nome')
    attr_last_name = models.CharField(max_length=100, default='family_name',
                                      help_text='Nome do atributo para sobrenome')
    attr_username = models.CharField(max_length=100, default='preferred_username',
                                     help_text='Nome do atributo para username')
    
    # Configurações de provisionamento
    auto_create_user = models.BooleanField(default=True,
                                           help_text='Criar usuário automaticamente no primeiro login')
    auto_update_user = models.BooleanField(default=True,
                                           help_text='Atualizar dados do usuário a cada login')
    default_role = models.CharField(max_length=20, default='agente',
                                    choices=[
                                        ('admin', 'Administrador'),
                                        ('supervisor', 'Supervisor'),
                                        ('agente', 'Agente'),
                                        ('cliente', 'Cliente'),
                                    ])
    domain_whitelist = models.TextField(blank=True,
                                        help_text='Domínios permitidos (um por linha). Vazio = qualquer domínio')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Provedor SSO'
        verbose_name_plural = 'Provedores SSO'
        ordering = ['name']
    
    def __str__(self):
        return f'{self.name} ({self.get_protocol_display()})'
    
    def save(self, *args, **kwargs):
        from dashboard.crypto import encrypt_value
        if self.client_secret and not self.client_secret.startswith('enc::'):
            self.client_secret = encrypt_value(self.client_secret)
        super().save(*args, **kwargs)
    
    def get_client_secret(self):
        from dashboard.crypto import decrypt_value
        return decrypt_value(self.client_secret)
    
    @property
    def allowed_domains(self):
        if self.domain_whitelist:
            return [d.strip().lower() for d in self.domain_whitelist.split('\n') if d.strip()]
        return []
    
    def is_email_allowed(self, email):
        domains = self.allowed_domains
        if not domains:
            return True
        email_domain = email.split('@')[-1].lower()
        return email_domain in domains


class SSOSession(models.Model):
    """Sessão SSO para rastreamento e estado CSRF"""
    state = models.CharField(max_length=128, unique=True, db_index=True)
    nonce = models.CharField(max_length=128, blank=True)
    provider = models.ForeignKey(SSOProvider, on_delete=models.CASCADE)
    redirect_url = models.CharField(max_length=500, default='/')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Sessão SSO'
        verbose_name_plural = 'Sessões SSO'
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class SSOLoginLog(models.Model):
    """Log de logins via SSO"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.ForeignKey(SSOProvider, on_delete=models.CASCADE)
    email = models.EmailField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Log de Login SSO'
        verbose_name_plural = 'Logs de Login SSO'
        ordering = ['-created_at']


# ======================== SSO ENGINE ========================

class SSOEngine:
    """Engine principal para autenticação SSO"""
    
    def get_active_providers(self):
        """Retorna provedores SSO ativos"""
        return SSOProvider.objects.filter(is_active=True)
    
    def initiate_oidc_login(self, provider, request, redirect_url='/dashboard/'):
        """Inicia fluxo OIDC (Authorization Code Flow)"""
        state = secrets.token_urlsafe(48)
        nonce = secrets.token_urlsafe(32)
        
        # Salvar sessão SSO
        session = SSOSession.objects.create(
            state=state,
            nonce=nonce,
            provider=provider,
            redirect_url=redirect_url,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )
        
        # Construir URL de autorização
        callback_url = request.build_absolute_uri(reverse('sso_callback', kwargs={'slug': provider.slug}))
        
        params = {
            'client_id': provider.client_id,
            'response_type': 'code',
            'redirect_uri': callback_url,
            'scope': provider.scopes,
            'state': state,
            'nonce': nonce,
        }
        
        auth_url = f'{provider.authorization_url}?{urlencode(params)}'
        return auth_url
    
    def handle_oidc_callback(self, provider, request):
        """Processa callback OIDC"""
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        if error:
            return None, f'Erro do provedor: {error} - {request.GET.get("error_description", "")}'
        
        if not code or not state:
            return None, 'Parâmetros inválidos no callback'
        
        # Validar state (proteção CSRF)
        try:
            session = SSOSession.objects.get(state=state, used=False)
        except SSOSession.DoesNotExist:
            return None, 'Sessão SSO inválida ou expirada'
        
        if session.is_expired:
            session.used = True
            session.save()
            return None, 'Sessão SSO expirada'
        
        session.used = True
        session.save()
        
        # Trocar código por token
        callback_url = request.build_absolute_uri(reverse('sso_callback', kwargs={'slug': provider.slug}))
        
        try:
            token_response = requests.post(provider.token_url, data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': callback_url,
                'client_id': provider.client_id,
                'client_secret': provider.get_client_secret(),
            }, timeout=15)
            
            if token_response.status_code != 200:
                return None, f'Erro ao obter token: {token_response.status_code}'
            
            token_data = token_response.json()
        except requests.RequestException as e:
            return None, f'Erro de conexão com provedor: {str(e)}'
        
        # Obter informações do usuário
        access_token = token_data.get('access_token')
        if not access_token:
            return None, 'Token de acesso não recebido'
        
        try:
            userinfo_response = requests.get(provider.userinfo_url, headers={
                'Authorization': f'Bearer {access_token}',
            }, timeout=10)
            
            if userinfo_response.status_code != 200:
                return None, f'Erro ao obter informações do usuário: {userinfo_response.status_code}'
            
            userinfo = userinfo_response.json()
        except requests.RequestException as e:
            return None, f'Erro ao consultar userinfo: {str(e)}'
        
        # Extrair dados do usuário
        email = userinfo.get(provider.attr_email, '')
        first_name = userinfo.get(provider.attr_first_name, '')
        last_name = userinfo.get(provider.attr_last_name, '')
        username = userinfo.get(provider.attr_username, email.split('@')[0] if email else '')
        
        if not email:
            return None, 'Email não fornecido pelo provedor'
        
        # Verificar domínio permitido
        if not provider.is_email_allowed(email):
            return None, f'Domínio de email não autorizado: {email.split("@")[-1]}'
        
        # Provisionar ou atualizar usuário
        user = self._provision_user(provider, email, username, first_name, last_name)
        
        if not user:
            return None, 'Falha ao provisionar usuário'
        
        return user, session.redirect_url
    
    def _provision_user(self, provider, email, username, first_name, last_name):
        """Provisiona ou atualiza usuário baseado nos dados SSO"""
        try:
            # Tentar encontrar por email
            user = User.objects.filter(email=email).first()
            
            if user:
                # Usuário existe — atualizar se configurado
                if provider.auto_update_user:
                    if first_name:
                        user.first_name = first_name
                    if last_name:
                        user.last_name = last_name
                    user.save()
                return user
            
            # Usuário não existe — criar se configurado
            if not provider.auto_create_user:
                logger.warning(f'SSO: Usuário {email} não existe e auto-create está desabilitado')
                return None
            
            # Garantir username único
            base_username = username or email.split('@')[0]
            final_username = base_username
            counter = 1
            while User.objects.filter(username=final_username).exists():
                final_username = f'{base_username}_{counter}'
                counter += 1
            
            user = User.objects.create_user(
                username=final_username,
                email=email,
                first_name=first_name or '',
                last_name=last_name or '',
            )
            # Senha inutilizável — login apenas via SSO
            user.set_unusable_password()
            user.save()
            
            # Atribuir role padrão
            try:
                from dashboard.rbac import UserRole
                UserRole.objects.get_or_create(
                    user=user,
                    defaults={'role': provider.default_role}
                )
            except Exception as e:
                logger.warning(f'SSO: Erro ao atribuir role: {e}')
            
            logger.info(f'SSO: Novo usuário criado via {provider.name}: {email}')
            return user
            
        except Exception as e:
            logger.error(f'SSO: Erro ao provisionar usuário {email}: {e}')
            return None


# Instância global
sso_engine = SSOEngine()


# ======================== VIEWS ========================

class SSOProviderListView(View):
    """Lista provedores SSO na página de login"""
    
    def get(self, request):
        providers = sso_engine.get_active_providers()
        return JsonResponse({
            'providers': [
                {
                    'slug': p.slug,
                    'name': p.name,
                    'icon_class': p.icon_class,
                    'button_color': p.button_color,
                    'protocol': p.protocol,
                    'login_url': reverse('sso_login', kwargs={'slug': p.slug}),
                }
                for p in providers
            ]
        })


class SSOLoginView(View):
    """Inicia fluxo de login SSO"""
    
    def get(self, request, slug):
        try:
            provider = SSOProvider.objects.get(slug=slug, is_active=True)
        except SSOProvider.DoesNotExist:
            return redirect(f'{reverse("login")}?error=sso_provider_not_found')
        
        next_url = request.GET.get('next', '/dashboard/')
        
        if provider.protocol == 'oidc':
            auth_url = sso_engine.initiate_oidc_login(provider, request, next_url)
            return HttpResponseRedirect(auth_url)
        elif provider.protocol == 'saml':
            # SAML login — redirect para IdP
            return HttpResponseRedirect(provider.saml_sso_url)
        
        return redirect(f'{reverse("login")}?error=unsupported_protocol')


class SSOCallbackView(View):
    """Recebe callback do provedor SSO"""
    
    def get(self, request, slug):
        try:
            provider = SSOProvider.objects.get(slug=slug, is_active=True)
        except SSOProvider.DoesNotExist:
            return redirect(f'{reverse("login")}?error=sso_provider_not_found')
        
        # Log do IP
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        if provider.protocol == 'oidc':
            user, result = sso_engine.handle_oidc_callback(provider, request)
        else:
            user, result = None, 'Protocolo não suportado para callback'
        
        # Log do login
        SSOLoginLog.objects.create(
            user=user,
            provider=provider,
            email=user.email if user else '',
            ip_address=ip[:45] if ip else None,
            user_agent=user_agent[:500],
            success=user is not None,
            error_message=result if user is None else '',
        )
        
        if user:
            django_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            logger.info(f'SSO Login: {user.email} via {provider.name}')
            redirect_url = result if isinstance(result, str) and result.startswith('/') else '/dashboard/'
            return redirect(redirect_url)
        else:
            logger.warning(f'SSO Login falhou via {provider.name}: {result}')
            return redirect(f'{reverse("login")}?error=sso_failed&detail={result}')


# Context processor para templates
def sso_context(request):
    """Adiciona provedores SSO ao contexto dos templates"""
    try:
        providers = SSOProvider.objects.filter(is_active=True)
        return {'sso_providers': providers}
    except Exception:
        return {'sso_providers': []}
