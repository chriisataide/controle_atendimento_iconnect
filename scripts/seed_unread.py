#!/usr/bin/env python
"""Criar notificações de teste não lidas."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')
import django; django.setup()

from dashboard.models import Notification, Ticket
from django.contrib.auth.models import User

admin = User.objects.get(username='admin')
ticket = Ticket.objects.first()

for title, ntype, msg in [
    ('URGENTE: SLA Violado', 'sla_breach', 'Ticket #{} excedeu o prazo!'.format(ticket.numero)),
    ('Novo ticket aberto', 'new_ticket', 'Ticket #{}: Problema critico no servidor'.format(ticket.numero)),
    ('Ticket atribuido a voce', 'ticket_assigned', 'Ticket #{} foi atribuido a voce'.format(ticket.numero)),
]:
    Notification.objects.create(
        user=admin, type=ntype, title=title, message=msg,
        icon='notifications', color='danger' if 'SLA' in title else 'primary',
        read=False, ticket=ticket,
    )

total = Notification.objects.filter(user=admin).count()
unread = Notification.objects.filter(user=admin, read=False).count()
print('Total: {}, Nao lidas: {}'.format(total, unread))
