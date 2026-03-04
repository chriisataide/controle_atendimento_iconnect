#!/usr/bin/env python
import os
import sys

os.environ["DJANGO_SETTINGS_MODULE"] = "controle_atendimento.settings"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.conf import settings

settings.ALLOWED_HOSTS = ["*"]

from django.test import Client

c = Client()
c.login(username="admin", password="admin")

print("=" * 60)
print("TESTE DAS PAGINAS DE USUARIO")
print("=" * 60)

# Test user list
r = c.get("/dashboard/users/")
print(f"\n1. User List: HTTP {r.status_code}")
if r.status_code == 200:
    content = r.content.decode()
    checks = [
        "Gerenciar Usuários",
        "user-stats-card",
        "search-box",
        "filter-chip",
        "user-avatar-circle",
        "total_users",
    ]
    for check in checks:
        found = check in content
        status = "OK" if found else "MISSING"
        print(f"  [{status}] {check}")
else:
    print(f"  ERRO: Retornou {r.status_code}")

# Test user create
r = c.get("/dashboard/users/novo/")
print(f"\n2. User Create: HTTP {r.status_code}")
if r.status_code == 200:
    content = r.content.decode()
    checks = [
        "Criar Novo Usuário",
        "create-header",
        "avatar-preview",
        "section-label",
        "#06b6d4",
        "id_username",
        "id_password1",
    ]
    for check in checks:
        found = check in content
        status = "OK" if found else "MISSING"
        print(f"  [{status}] {check}")

    # Check OFF-PALETTE colors are GONE
    bad_colors = ["#ff6b6b", "#4ecdc4"]
    for color in bad_colors:
        found = color in content
        status = "GONE (good)" if not found else "STILL PRESENT (bad)"
        print(f"  [{status}] old color {color}")
else:
    print(f"  ERRO: Retornou {r.status_code}")

# Test profile
r = c.get("/dashboard/profile/")
print(f"\n3. Profile: HTTP {r.status_code}")
if r.status_code == 200:
    content = r.content.decode()
    checks = [
        "Meu Perfil",
        "profile-header-card",
        "telefone_alternativo",
        "cidade",
        "estado",
        "cep",
        "cargo",
        "departamento",
        "subsection-label",
        "professional-content",
        "perfil_completo",
    ]
    for check in checks:
        found = check in content
        status = "OK" if found else "MISSING"
        print(f"  [{status}] {check}")
else:
    print(f"  ERRO: Retornou {r.status_code}")

print("\n" + "=" * 60)
print("TESTE CONCLUIDO")
print("=" * 60)
