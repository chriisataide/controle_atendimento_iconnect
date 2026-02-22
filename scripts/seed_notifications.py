#!/usr/bin/env python
"""Seed script para criar notificações de teste para o admin."""
import os
import sys
import random
from datetime import timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')

import django
django.setup()

from dashboard.models import Notification, Ticket
from django.contrib.auth.models import User
from django.utils import timezone


def seed_notifications():
    admin = User.objects.get(username='admin')
    tickets = list(Ticket.objects.all()[:20])

    scenarios = [
        ('new_ticket', 'Novo Ticket Criado', 'Ticket #{num}: {titulo}', 'primary', 'assignment'),
        ('new_ticket', 'Novo Ticket Criado', 'Ticket #{num}: {titulo}', 'primary', 'assignment'),
        ('ticket_assigned', 'Ticket Atribuído a Você', 'Ticket #{num} foi atribuído a você: {titulo}', 'info', 'person_add'),
        ('ticket_status_change', 'Status Alterado', 'Ticket #{num} mudou para: Em Andamento', 'warning', 'update'),
        ('sla_warning', 'SLA Próximo do Vencimento', 'Ticket #{num} vence em 30 minutos!', 'warning', 'warning'),
        ('sla_warning', 'SLA em Risco', 'Ticket #{num} precisa de atenção urgente', 'warning', 'warning'),
        ('sla_breach', 'SLA VIOLADO', 'Ticket #{num} excedeu o prazo de atendimento!', 'danger', 'error'),
        ('new_interaction', 'Nova Interação', 'Nova resposta no ticket #{num}', 'success', 'message'),
        ('new_interaction', 'Novo Comentário', 'Comentário adicionado ao ticket #{num}', 'success', 'message'),
        ('system_alert', 'Alerta do Sistema', 'Backup concluído com sucesso', 'info', 'info'),
        ('system_alert', 'Manutenção Programada', 'Manutenção agendada para amanhã às 03:00', 'info', 'info'),
        ('new_ticket', 'Ticket Crítico Aberto', 'Ticket #{num}: Sistema indisponível - URGENTE', 'danger', 'priority_high'),
        ('ticket_assigned', 'Redistribuição Automática', 'Ticket #{num} redistribuído pelo sistema de balanceamento', 'info', 'person_add'),
        ('ticket_status_change', 'Ticket Resolvido', 'Ticket #{num} foi resolvido pelo agente', 'success', 'check_circle'),
        ('system_alert', 'Relatório Gerado', 'Relatório semanal de performance disponível para download', 'info', 'assessment'),
    ]

    created = 0
    for i, (ntype, title, msg_tpl, color, icon) in enumerate(scenarios):
        ticket = random.choice(tickets) if tickets else None
        msg = msg_tpl.format(
            num=ticket.numero if ticket else '???',
            titulo=ticket.titulo if ticket else 'Ticket de teste'
        )

        Notification.objects.create(
            user=admin,
            type=ntype,
            title=title,
            message=msg,
            icon=icon,
            color=color,
            read=random.choice([True, False, False]),
            ticket=ticket,
            created_at=timezone.now() - timedelta(
                hours=random.randint(0, 48),
                minutes=random.randint(0, 59)
            )
        )
        created += 1

    total = Notification.objects.filter(user=admin).count()
    unread = Notification.objects.filter(user=admin, read=False).count()
    print(f'Criadas {created} notificações para admin')
    print(f'Total: {total}, Não lidas: {unread}')


if __name__ == '__main__':
    seed_notifications()
