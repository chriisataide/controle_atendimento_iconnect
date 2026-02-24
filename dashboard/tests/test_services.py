"""
Testes de Services — ticket_service, ai_service, cache, gamification, SLA.
"""
from unittest.mock import patch, MagicMock
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.models import (
    Ticket, Cliente, StatusTicket, PrioridadeTicket,
    SLAPolicy, SLAHistory, WorkflowRule,
    GamificationBadge, AgentBadge, AgentLeaderboard,
)
from .factories import (
    UserFactory, ClienteFactory, CategoriaFactory,
    TicketFactory, SLAPolicyFactory, PerfilAgenteFactory,
)


class TicketServiceTest(TestCase):
    def test_create_ticket_via_service(self):
        from dashboard.services.ticket_service import TicketService
        svc = TicketService()
        cliente = ClienteFactory()
        user = UserFactory()
        result = svc.create_ticket(
            titulo='Teste via Service',
            descricao='Body',
            cliente_id=cliente.id,
            user=user,
        )
        self.assertIsNotNone(result)

    def test_update_ticket_status(self):
        from dashboard.services.ticket_service import TicketService
        svc = TicketService()
        t = TicketFactory(status=StatusTicket.ABERTO)
        user = UserFactory()
        result = svc.update_ticket(
            ticket_id=t.id,
            user=user,
            status=StatusTicket.EM_ANDAMENTO,
        )
        self.assertIsNotNone(result)


class CacheServiceTest(TestCase):
    def test_get_set(self):
        from dashboard.services.cache_service import CacheService
        svc = CacheService()
        svc.set('test_key', {'data': 123}, timeout=60)
        val = svc.get('test_key')
        self.assertEqual(val, {'data': 123})

    def test_delete(self):
        from dashboard.services.cache_service import CacheService
        svc = CacheService()
        svc.set('del_key', 'value')
        svc.delete('del_key')
        self.assertIsNone(svc.get('del_key'))


class AnalyticsServiceTest(TestCase):
    def test_get_overview_metrics(self):
        from dashboard.services.analytics_service import AnalyticsService
        svc = AnalyticsService()
        TicketFactory.create_batch(3)
        metrics = svc.get_overview_metrics()
        self.assertIsNotNone(metrics)

    def test_get_agent_performance(self):
        from dashboard.services.analytics_service import AnalyticsService
        svc = AnalyticsService()
        agent = PerfilAgenteFactory()
        TicketFactory(agente=agent.user, status=StatusTicket.FECHADO)
        result = svc.get_agent_performance()
        self.assertIsNotNone(result)


class GamificationServiceTest(TestCase):
    def test_award_points(self):
        from dashboard.services.gamification_service import GamificationService
        svc = GamificationService()
        user = UserFactory()
        result = svc.award_points(user, 'ticket_resolved', 10)
        self.assertTrue(result)


class SLACalculatorTest(TestCase):
    def test_calculate_deadline(self):
        from dashboard.services.sla_calculator import sla_calculator
        t = TicketFactory(prioridade=PrioridadeTicket.ALTA)
        deadline = sla_calculator.calculate_sla_deadline(t)
        self.assertIsNotNone(deadline)

    def test_sla_with_policy(self):
        cat = CategoriaFactory()
        policy = SLAPolicyFactory(categoria=cat, prioridade='alta')
        t = TicketFactory(prioridade='alta', categoria=cat)
        from dashboard.services.sla_calculator import sla_calculator
        deadline = sla_calculator.calculate_sla_deadline(t)
        self.assertIsNotNone(deadline)


class WorkflowEngineTest(TestCase):
    def test_execute_workflow_no_rules(self):
        from dashboard.workflows import workflow_engine
        t = TicketFactory()
        results = workflow_engine.execute_workflow(t, 'ticket_created')
        self.assertEqual(results, [])

    def test_execute_workflow_with_rule(self):
        from dashboard.workflows import workflow_engine
        from dashboard.models import WorkflowRule
        t = TicketFactory(prioridade='alta')
        WorkflowRule.objects.create(
            name='Test Rule',
            trigger_event='ticket_created',
            conditions='{"prioridade": ["alta"]}',
            actions='{"add_comment": {"comment": "Auto comment", "public": false}}',
            is_active=True,
            priority=5,
        )
        results = workflow_engine.execute_workflow(t, 'ticket_created')
        self.assertGreater(len(results), 0)

    def test_workflow_metrics(self):
        from dashboard.workflows import workflow_engine
        metrics = workflow_engine.get_workflow_metrics(days=30)
        self.assertIn('total_executions', metrics)
        self.assertIn('success_rate', metrics)
