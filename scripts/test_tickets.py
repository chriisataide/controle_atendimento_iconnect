"""Test all ticket URLs"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')

import django
django.setup()

from django.conf import settings
settings.ALLOWED_HOSTS = ['*']

from django.test import Client
from dashboard.models import Ticket

c = Client()
login = c.login(username='admin', password='admin')
print(f'Login: {login}')

urls = [
    ('/dashboard/tickets/', 'Ticket List'),
    ('/dashboard/tickets/novo/', 'Ticket Create'),
    ('/dashboard/api/tickets-chart/', 'Tickets Chart API'),
    ('/dashboard/export/tickets/', 'Export Tickets'),
]

for url, name in urls:
    try:
        resp = c.get(url)
        status = resp.status_code
        ok = '✅' if status == 200 else '⚠️' if status == 302 else '❌'
        print(f'{ok} {name}: {status} - {url}')
        if status >= 400:
            content = resp.content[:300].decode('utf-8', errors='replace')
            print(f'   Error: {content[:200]}')
    except Exception as e:
        print(f'❌ {name}: ERROR - {e}')

# Test detail/update for first ticket
first = Ticket.objects.first()
if first:
    for suffix, name in [('', 'Detail'), ('/editar/', 'Update')]:
        url = f'/dashboard/tickets/{first.pk}/{suffix}'.replace('//', '/')
        try:
            resp = c.get(url)
            status = resp.status_code
            ok = '✅' if status == 200 else '⚠️' if status == 302 else '❌'
            print(f'{ok} Ticket {name} ({first.numero}): {status} - {url}')
            if status >= 400:
                content = resp.content[:300].decode('utf-8', errors='replace')
                print(f'   Error: {content[:200]}')
        except Exception as e:
            print(f'❌ Ticket {name}: ERROR - {e}')

# Test API endpoints
api_urls = [
    (f'/dashboard/api/ticket-itens/{first.pk}/' if first else None, 'Ticket Items API'),
    (f'/dashboard/api/ticket-financeiro/{first.pk}/' if first else None, 'Ticket Financeiro API'),
]
for url, name in api_urls:
    if not url:
        continue
    try:
        resp = c.get(url)
        status = resp.status_code
        ok = '✅' if status == 200 else '❌'
        print(f'{ok} {name}: {status} - {url}')
        if status >= 400:
            content = resp.content[:300].decode('utf-8', errors='replace')
            print(f'   Error: {content[:200]}')
    except Exception as e:
        print(f'❌ {name}: ERROR - {e}')

# KPI verification via direct view call
from dashboard.views import TicketListView
from dashboard.models import Ticket, CategoriaTicket
from django.contrib.auth.models import User
from django.db.models import Avg, F, Count
from datetime import datetime

total = Ticket.objects.count()
abertos = Ticket.objects.filter(status='aberto').count()
andamento = Ticket.objects.filter(status='em_andamento').count()
resolvidos = Ticket.objects.filter(status='resolvido').count()
criticos = Ticket.objects.filter(prioridade='critica').count()
nao_atribuidos = Ticket.objects.filter(agente__isnull=True).count()
categorias = CategoriaTicket.objects.count()
agentes = User.objects.filter(perfilagente__isnull=False).count()

print(f'\n📊 Dados no Banco:')
print(f'   Total tickets: {total}')
print(f'   Abertos: {abertos}')
print(f'   Em andamento: {andamento}')
print(f'   Resolvidos: {resolvidos}')
print(f'   Críticos: {criticos}')
print(f'   Não atribuídos: {nao_atribuidos}')
print(f'   Categorias: {categorias}')
print(f'   Agentes: {agentes}')

# Check list page contains expected HTML
resp = c.get('/dashboard/tickets/')
content = resp.content.decode('utf-8')
checks = [
    ('kpi_total' in content or str(total) in content, f'Total KPI ({total}) in page'),
    ('Tickets Abertos' in content or 'Abertos' in content, 'Abertos label in page'),  
    ('filtrar' in content.lower() or 'Filtrar' in content, 'Filter button in page'),
    ('confirmation_number' in content, 'Ticket icon in page'),
]
print(f'\n🔍 Verificação do HTML:')
for ok, desc in checks:
    print(f'   {"✅" if ok else "❌"} {desc}')

print('\n✅ Todos os testes concluídos!')
