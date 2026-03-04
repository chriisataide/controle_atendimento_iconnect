"""
Management command para configurar RBAC (roles, groups, permissoes).
Uso: python manage.py setup_rbac
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from dashboard.utils.rbac import ROLE_ADMIN, assign_role, setup_groups_and_permissions


class Command(BaseCommand):
    help = "Configura groups e permissoes de RBAC e atribui role admin ao superuser"

    def handle(self, *args, **options):
        self.stdout.write("Configurando groups e permissoes...")
        setup_groups_and_permissions()
        self.stdout.write(self.style.SUCCESS("Groups e permissoes configurados."))

        # Atribuir admin a todos os superusers existentes
        superusers = User.objects.filter(is_superuser=True)
        for su in superusers:
            assign_role(su, ROLE_ADMIN)
            self.stdout.write(f"  {su.username} -> admin")

        self.stdout.write(self.style.SUCCESS("RBAC configurado com sucesso!"))
