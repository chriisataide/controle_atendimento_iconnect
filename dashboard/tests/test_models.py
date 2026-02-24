"""
Testes de Models — Cobertura completa dos modelos do iConnect.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from dashboard.models import (
    Cliente, CategoriaTicket, Ticket, PrioridadeTicket, StatusTicket,
    SLAPolicy, SLAHistory, SLAAlert, SLAViolation,
    InteracaoTicket, TicketAnexo, PerfilAgente, PerfilUsuario,
    WorkflowRule, WorkflowExecution, Notification, PontoDeVenda,
    CannedResponse, Tag, WebhookEndpoint, APIKey, TimeEntry,
    GamificationBadge, AgentBadge, AgentLeaderboard,
    CustomerHealthScore,
)
from .factories import (
    UserFactory, AdminFactory, ClienteFactory, CategoriaFactory,
    TicketFactory, SLAPolicyFactory, PerfilAgenteFactory, WorkflowRuleFactory,
)


class ClienteModelTest(TestCase):
    def test_criacao(self):
        c = ClienteFactory()
        self.assertTrue(c.pk)
        self.assertIn('@', c.email)

    def test_str(self):
        c = ClienteFactory(nome='João Silva')
        self.assertEqual(str(c), 'João Silva')

    def test_email_unico(self):
        ClienteFactory(email='dup@test.com')
        with self.assertRaises(Exception):
            ClienteFactory(email='dup@test.com')

    def test_user_vinculado(self):
        user = UserFactory()
        c = ClienteFactory(user=user)
        self.assertEqual(c.user, user)


class TicketModelTest(TestCase):
    def test_numero_gerado_automaticamente(self):
        t = TicketFactory()
        self.assertTrue(t.numero.startswith('TK-'))

    def test_status_padrao_aberto(self):
        t = TicketFactory()
        self.assertEqual(t.status, StatusTicket.ABERTO)

    def test_resolvido_em_setado_ao_resolver(self):
        t = TicketFactory()
        t.status = StatusTicket.RESOLVIDO
        t.save()
        t.refresh_from_db()
        self.assertIsNotNone(t.resolvido_em)

    def test_fechado_em_setado_ao_fechar(self):
        t = TicketFactory()
        t.status = StatusTicket.FECHADO
        t.save()
        t.refresh_from_db()
        self.assertIsNotNone(t.fechado_em)

    def test_tags_list(self):
        t = TicketFactory(tags='python, django, api')
        self.assertEqual(t.get_tags_list(), ['python', 'django', 'api'])

    def test_tags_list_vazia(self):
        t = TicketFactory(tags='')
        self.assertEqual(t.get_tags_list(), [])

    def test_str(self):
        t = TicketFactory(titulo='Teste')
        self.assertIn('Teste', str(t))

    def test_tipos_itil(self):
        for tipo, _ in Ticket.TIPO_CHOICES:
            t = TicketFactory(tipo=tipo)
            self.assertEqual(t.tipo, tipo)

    def test_parent_child_relationship(self):
        parent = TicketFactory()
        child = TicketFactory(parent_ticket=parent)
        self.assertEqual(child.parent_ticket, parent)
        self.assertIn(child, parent.sub_tickets.all())

    def test_watchers(self):
        t = TicketFactory()
        user = UserFactory()
        t.watchers.add(user)
        self.assertIn(user, t.watchers.all())

    def test_merged_into(self):
        t1 = TicketFactory()
        t2 = TicketFactory(merged_into=t1)
        self.assertEqual(t2.merged_into, t1)
        self.assertIn(t2, t1.merged_from.all())


class SLAPolicyModelTest(TestCase):
    def test_criacao(self):
        p = SLAPolicyFactory()
        self.assertTrue(p.is_active)

    def test_str(self):
        p = SLAPolicyFactory(name='SLA Crítica')
        self.assertEqual(str(p), 'SLA Crítica')

    def test_unique_together_categoria_prioridade(self):
        cat = CategoriaFactory()
        SLAPolicyFactory(categoria=cat, prioridade='alta')
        with self.assertRaises(Exception):
            SLAPolicyFactory(categoria=cat, prioridade='alta')


class InteracaoModelTest(TestCase):
    def test_criacao(self):
        t = TicketFactory()
        u = UserFactory()
        i = InteracaoTicket.objects.create(
            ticket=t, usuario=u, mensagem='Resposta', tipo='resposta'
        )
        self.assertIn(t.numero, str(i))

    def test_tipos(self):
        for tipo, _ in InteracaoTicket.TIPO_CHOICES:
            t = TicketFactory()
            u = UserFactory()
            i = InteracaoTicket.objects.create(
                ticket=t, usuario=u, mensagem='Test', tipo=tipo
            )
            self.assertEqual(i.tipo, tipo)


class PerfilAgenteModelTest(TestCase):
    def test_tickets_ativos(self):
        agente = PerfilAgenteFactory()
        TicketFactory(agente=agente.user, status=StatusTicket.ABERTO)
        TicketFactory(agente=agente.user, status=StatusTicket.EM_ANDAMENTO)
        TicketFactory(agente=agente.user, status=StatusTicket.FECHADO)
        self.assertEqual(agente.tickets_ativos, 2)

    def test_str(self):
        u = UserFactory(first_name='Carlos', last_name='Silva')
        p = PerfilAgenteFactory(user=u)
        self.assertIn('Carlos', str(p))


class WorkflowRuleModelTest(TestCase):
    def test_criacao(self):
        r = WorkflowRuleFactory()
        self.assertTrue(r.is_active)

    def test_ordering(self):
        r1 = WorkflowRuleFactory(priority=1)
        r2 = WorkflowRuleFactory(priority=10)
        rules = list(WorkflowRule.objects.all())
        self.assertEqual(rules[0], r2)

    def test_str(self):
        r = WorkflowRuleFactory(name='Auto Escalação')
        self.assertEqual(str(r), 'Auto Escalação')


class GamificationModelTest(TestCase):
    def test_badge_criacao(self):
        b = GamificationBadge.objects.create(
            nome='Speed Demon', descricao='Resolve rapido',
            criteria={'metric': 'tickets_resolved', 'threshold': 50}
        )
        self.assertEqual(str(b), 'Speed Demon')

    def test_agent_badge_unique(self):
        u = UserFactory()
        b = GamificationBadge.objects.create(
            nome='Badge', descricao='Test',
            criteria={'metric': 'x', 'threshold': 1}
        )
        AgentBadge.objects.create(usuario=u, badge=b)
        with self.assertRaises(Exception):
            AgentBadge.objects.create(usuario=u, badge=b)


class NotificationModelTest(TestCase):
    def test_criacao(self):
        u = UserFactory()
        n = Notification.objects.create(
            user=u, type='new_ticket', message='Novo ticket criado'
        )
        self.assertFalse(n.read)
        self.assertTrue(n.pk)


class CannedResponseModelTest(TestCase):
    def test_criacao(self):
        u = UserFactory()
        cr = CannedResponse.objects.create(
            title='Saudação', content='Olá, como posso ajudar?',
            category='suporte', created_by=u
        )
        self.assertEqual(str(cr), 'Saudação')
