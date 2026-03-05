"""
RBAC - Role-Based Access Control para iConnect
Roles: admin, supervisor, agente, cliente
"""

import functools
import logging

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import PermissionDenied
from django.db import models
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes de Roles
# ---------------------------------------------------------------------------

ROLE_ADMIN = "admin"
ROLE_GERENTE = "gerente"
ROLE_SUPERVISOR = "supervisor"
ROLE_TECNICO_SENIOR = "tecnico_senior"
ROLE_AGENTE = "agente"
ROLE_FINANCEIRO = "financeiro"
ROLE_VISUALIZADOR = "visualizador"
ROLE_CLIENTE = "cliente"

ALL_ROLES = [
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_SUPERVISOR,
    ROLE_TECNICO_SENIOR,
    ROLE_AGENTE,
    ROLE_FINANCEIRO,
    ROLE_VISUALIZADOR,
    ROLE_CLIENTE,
]

# Mapeamento de permissoes por role (app_label.codename)
ROLE_PERMISSIONS = {
    ROLE_ADMIN: [
        # Tudo --- admin recebe is_staff=True + superuser
    ],
    ROLE_GERENTE: [
        # Gestão estratégica: dashboards executivos, relatórios, visão geral
        "dashboard.view_ticket",
        "dashboard.view_cliente",
        "dashboard.change_cliente",
        "dashboard.view_interacaoticket",
        "dashboard.view_slapolicy",
        "dashboard.view_slahistory",
        "dashboard.view_slaalert",
        "dashboard.view_slaviolation",
        "dashboard.view_perfilagente",
        "dashboard.view_categoriaticket",
        "dashboard.view_auditevent",
        "dashboard.view_securityalert",
    ],
    ROLE_SUPERVISOR: [
        "dashboard.view_ticket",
        "dashboard.change_ticket",
        "dashboard.delete_ticket",
        "dashboard.add_ticket",
        "dashboard.view_cliente",
        "dashboard.change_cliente",
        "dashboard.view_interacaoticket",
        "dashboard.add_interacaoticket",
        "dashboard.view_slapolicy",
        "dashboard.change_slapolicy",
        "dashboard.add_slapolicy",
        "dashboard.view_slahistory",
        "dashboard.view_slaalert",
        "dashboard.view_slaviolation",
        "dashboard.view_perfilagente",
        "dashboard.change_perfilagente",
        "dashboard.view_categoriaticket",
        "dashboard.change_categoriaticket",
        "dashboard.add_categoriaticket",
        "dashboard.view_auditevent",
        "dashboard.view_securityalert",
    ],
    ROLE_TECNICO_SENIOR: [
        # Agente com mais autonomia: relatórios, gerenciamento de filas
        "dashboard.view_ticket",
        "dashboard.change_ticket",
        "dashboard.add_ticket",
        "dashboard.delete_ticket",
        "dashboard.view_cliente",
        "dashboard.change_cliente",
        "dashboard.view_interacaoticket",
        "dashboard.add_interacaoticket",
        "dashboard.view_slapolicy",
        "dashboard.view_slahistory",
        "dashboard.view_slaalert",
        "dashboard.view_categoriaticket",
        "dashboard.view_perfilagente",
    ],
    ROLE_AGENTE: [
        "dashboard.view_ticket",
        "dashboard.change_ticket",
        "dashboard.add_ticket",
        "dashboard.view_cliente",
        "dashboard.view_interacaoticket",
        "dashboard.add_interacaoticket",
        "dashboard.view_categoriaticket",
    ],
    ROLE_FINANCEIRO: [
        # Gestão financeira: cobranças, custos, relatórios financeiros
        "dashboard.view_ticket",
        "dashboard.view_cliente",
        "dashboard.change_cliente",
        "dashboard.view_interacaoticket",
        "dashboard.view_categoriaticket",
    ],
    ROLE_VISUALIZADOR: [
        # Somente leitura: tickets e relatórios
        "dashboard.view_ticket",
        "dashboard.view_cliente",
        "dashboard.view_interacaoticket",
        "dashboard.view_slapolicy",
        "dashboard.view_slahistory",
        "dashboard.view_slaalert",
        "dashboard.view_slaviolation",
        "dashboard.view_categoriaticket",
        "dashboard.view_auditevent",
    ],
    ROLE_CLIENTE: [
        "dashboard.view_ticket",
        "dashboard.add_ticket",
        "dashboard.view_interacaoticket",
        "dashboard.add_interacaoticket",
    ],
}


# ---------------------------------------------------------------------------
# Model UserRole
# ---------------------------------------------------------------------------


class UserRole(models.Model):
    """Vinculo explicito entre usuario e role"""

    ROLE_CHOICES = [
        (ROLE_ADMIN, "Administrador"),
        (ROLE_GERENTE, "Gerente"),
        (ROLE_SUPERVISOR, "Supervisor"),
        (ROLE_TECNICO_SENIOR, "Técnico Sênior"),
        (ROLE_AGENTE, "Agente"),
        (ROLE_FINANCEIRO, "Financeiro"),
        (ROLE_VISUALIZADOR, "Visualizador"),
        (ROLE_CLIENTE, "Cliente"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="role_profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_AGENTE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Role de Usuario"
        verbose_name_plural = "Roles de Usuarios"

    def __str__(self):
        return f"{self.user.username} -> {self.get_role_display()}"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_user_role(user) -> str:
    """Retorna a role do usuario. Fallback para 'agente' se nao definida."""
    if not user or not user.is_authenticated:
        return ROLE_CLIENTE
    if user.is_superuser:
        return ROLE_ADMIN
    try:
        return user.role_profile.role
    except (UserRole.DoesNotExist, AttributeError):
        return ROLE_AGENTE


def user_has_role(user, *roles) -> bool:
    """Verifica se usuario possui alguma das roles informadas."""
    current = get_user_role(user)
    # Admin sempre tem acesso
    if current == ROLE_ADMIN:
        return True
    return current in roles


def assign_role(user: User, role: str):
    """Atribui role a um usuario, criando/atualizando UserRole e Group."""
    if role not in ALL_ROLES:
        raise ValueError(f"Role invalida: {role}")

    obj, created = UserRole.objects.update_or_create(user=user, defaults={"role": role})

    # Sincronizar com Django Groups
    group, _ = Group.objects.get_or_create(name=role)
    user.groups.clear()
    user.groups.add(group)

    # Flags especiais
    if role == ROLE_ADMIN:
        user.is_staff = True
        user.is_superuser = True
    elif role in (ROLE_GERENTE, ROLE_SUPERVISOR, ROLE_TECNICO_SENIOR, ROLE_FINANCEIRO):
        user.is_staff = True
        user.is_superuser = False
    else:
        user.is_staff = False
        user.is_superuser = False
    user.save(update_fields=["is_staff", "is_superuser"])

    return obj


def setup_groups_and_permissions():
    """Cria Groups e atribui permissoes. Chamar via management command."""

    for role_name, perm_strings in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=role_name)
        group.permissions.clear()

        for perm_str in perm_strings:
            app_label, codename = perm_str.split(".")
            try:
                perm = Permission.objects.get(content_type__app_label=app_label, codename=codename)
                group.permissions.add(perm)
            except Permission.DoesNotExist:
                logger.warning(f"Permissao nao encontrada: {perm_str}")

    logger.info("Groups e permissoes configurados com sucesso")


# ---------------------------------------------------------------------------
# Decorator @role_required
# ---------------------------------------------------------------------------


def role_required(*allowed_roles, redirect_url=None):
    """
    Decorator para views baseadas em funcao.
    Uso: @role_required("admin", "supervisor")
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.conf import settings

                return redirect(settings.LOGIN_URL)
            if not user_has_role(request.user, *allowed_roles):
                if redirect_url:
                    return redirect(redirect_url)
                raise PermissionDenied("Voce nao tem permissao para acessar esta pagina.")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Mixin para CBVs
# ---------------------------------------------------------------------------


class RoleRequiredMixin(AccessMixin):
    """
    Mixin para class-based views.
    Uso: class MyView(RoleRequiredMixin, TemplateView):
             allowed_roles = ["admin", "supervisor"]
    """

    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_has_role(request.user, *self.allowed_roles):
            raise PermissionDenied("Voce nao tem permissao para acessar esta pagina.")
        return super().dispatch(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Template context processor
# ---------------------------------------------------------------------------


def rbac_context(request):
    """Adiciona role e helpers ao contexto de templates."""
    if hasattr(request, "user") and request.user.is_authenticated:
        role = get_user_role(request.user)
        # Busca perfil do usuário para uso global nos templates
        user_perfil = None
        try:
            from dashboard.models import PerfilUsuario

            user_perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user, defaults={"telefone": ""})
        except Exception:
            pass
        return {
            "user_role": role,
            "is_admin": role == ROLE_ADMIN,
            "is_gerente": role in (ROLE_ADMIN, ROLE_GERENTE),
            "is_supervisor": role in (ROLE_ADMIN, ROLE_GERENTE, ROLE_SUPERVISOR),
            "is_tecnico_senior": role in (ROLE_ADMIN, ROLE_GERENTE, ROLE_SUPERVISOR, ROLE_TECNICO_SENIOR),
            "is_agente": role in (ROLE_ADMIN, ROLE_GERENTE, ROLE_SUPERVISOR, ROLE_TECNICO_SENIOR, ROLE_AGENTE),
            "is_financeiro": role in (ROLE_ADMIN, ROLE_GERENTE, ROLE_FINANCEIRO),
            "is_visualizador": role
            in (
                ROLE_ADMIN,
                ROLE_GERENTE,
                ROLE_SUPERVISOR,
                ROLE_TECNICO_SENIOR,
                ROLE_AGENTE,
                ROLE_FINANCEIRO,
                ROLE_VISUALIZADOR,
            ),
            "is_cliente": role == ROLE_CLIENTE,
            "user_perfil": user_perfil,
            "unread_notifications_count": _get_unread_count(request.user),
        }
    return {
        "user_role": ROLE_CLIENTE,
        "is_admin": False,
        "is_gerente": False,
        "is_supervisor": False,
        "is_tecnico_senior": False,
        "is_agente": False,
        "is_financeiro": False,
        "is_visualizador": False,
        "is_cliente": True,
        "user_perfil": None,
        "unread_notifications_count": 0,
    }


def _get_unread_count(user):
    """Retorna quantidade de notificações não lidas."""
    try:
        from dashboard.models import Notification
        return Notification.objects.filter(user=user, read=False).count()
    except Exception:
        return 0
