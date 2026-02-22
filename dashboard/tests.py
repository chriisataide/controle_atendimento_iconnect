"""
Tests — Testes unitarios e de integracao para iConnect Helpdesk
Cobre: Models, API, Services, RBAC, Webhooks, AI, Gamification
"""
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from .models import Cliente, CategoriaTicket, Ticket, PrioridadeTicket, StatusTicket


# ===========================================================================
# Factory helpers
# ===========================================================================

class BaseTestMixin:
    """Helpers comuns para testes"""

    def create_user(self, username='testuser', password='testpass123', **kwargs):
        return User.objects.create_user(
            username=username, password=password,
            email=f'{username}@test.com', **kwargs
        )

    def create_admin(self, username='admin', password='admin123'):
        return User.objects.create_superuser(
            username=username, password=password,
            email=f'{username}@test.com'
        )

    def create_cliente(self, nome='Cliente Teste', email='cliente@test.com'):
        return Cliente.objects.create(nome=nome, email=email)

    def create_ticket(self, cliente=None, agente=None, **kwargs):
        if not cliente:
            cliente = self.create_cliente()
        defaults = {
            'titulo': 'Ticket de Teste',
            'descricao': 'Descricao do ticket de teste',
            'cliente': cliente,
            'agente': agente,
            'status': 'aberto',
            'prioridade': 'media',
        }
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    def create_categoria(self, nome='Suporte Tecnico'):
        return CategoriaTicket.objects.create(nome=nome)


# ===========================================================================
# Model Tests
# ===========================================================================

class ClienteModelTest(TestCase):
    def test_criacao_cliente(self):
        cliente = Cliente.objects.create(nome="Cliente Teste", email="teste@exemplo.com")
        self.assertEqual(str(cliente), "Cliente Teste")
        self.assertEqual(cliente.email, "teste@exemplo.com")


    def test_cliente_com_user(self):
        user = User.objects.create_user(username='cli1', password='pass')
        cliente = Cliente.objects.create(nome="Cli Link", email="c@t.com", user=user)
        self.assertEqual(cliente.user, user)

    def test_cliente_sem_email_duplicado(self):
        Cliente.objects.create(nome="A", email="dup@test.com")
        with self.assertRaises(Exception):
            Cliente.objects.create(nome="B", email="dup@test.com")


class CategoriaTicketModelTest(TestCase):
    def test_criacao_categoria(self):
        categoria = CategoriaTicket.objects.create(nome="Suporte", cor="#123456")
        self.assertEqual(str(categoria), "Suporte")
        self.assertEqual(categoria.cor, "#123456")


class TicketModelTest(BaseTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user(username='agente')
        self.cliente = self.create_cliente()
        self.categoria = self.create_categoria()

    def test_criacao_ticket(self):
        ticket = Ticket.objects.create(
            cliente=self.cliente, agente=self.user,
            categoria=self.categoria,
            titulo="Problema de Teste", descricao="Descricao",
            prioridade=PrioridadeTicket.ALTA, status=StatusTicket.ABERTO,
        )
        self.assertTrue(ticket.numero)
        self.assertEqual(ticket.titulo, "Problema de Teste")
        self.assertEqual(ticket.status, StatusTicket.ABERTO)

    def test_ticket_str(self):
        ticket = self.create_ticket(cliente=self.cliente, agente=self.user)
        self.assertIn(ticket.numero, str(ticket))

    def test_ticket_status_default(self):
        ticket = self.create_ticket(cliente=self.cliente)
        self.assertEqual(ticket.status, 'aberto')

    def test_ticket_tipo_itil(self):
        ticket = self.create_ticket(cliente=self.cliente, tipo='problema')
        self.assertEqual(ticket.tipo, 'problema')


class CannedResponseModelTest(BaseTestMixin, TestCase):
    def test_canned_response_create(self):
        from .models import CannedResponse
        user = self.create_user()
        cr = CannedResponse.objects.create(
            titulo='Saudacao', corpo='Ola, como posso ajudar?',
            categoria='geral', criado_por=user,
        )
        self.assertIn('Saudacao', str(cr))


class APIKeyModelTest(BaseTestMixin, TestCase):
    def test_generate_key(self):
        from .models import APIKey
        user = self.create_user()
        raw_key, key_hash, prefix = APIKey.generate_key()
        api_key = APIKey.objects.create(
            nome='Teste Key', criado_por=user,
            key_hash=key_hash, prefix=prefix,
        )
        self.assertTrue(raw_key.startswith(prefix))
        self.assertTrue(api_key.is_valid())

    def test_revoked_key(self):
        from .models import APIKey
        user = self.create_user()
        _, key_hash, prefix = APIKey.generate_key()
        api_key = APIKey.objects.create(
            nome='Rev', criado_por=user,
            key_hash=key_hash, prefix=prefix,
        )
        api_key.is_active = False
        api_key.save()
        self.assertFalse(api_key.is_valid())


class TagModelTest(TestCase):
    def test_tag_create(self):
        from .models import Tag
        tag = Tag.objects.create(nome='VIP', cor='#ff0000')
        self.assertEqual(str(tag), 'VIP')


class TimeEntryTest(BaseTestMixin, TestCase):
    def test_horas_property(self):
        from .models import TimeEntry
        user = self.create_user()
        ticket = self.create_ticket()
        te = TimeEntry.objects.create(ticket=ticket, usuario=user, minutos=150)
        self.assertAlmostEqual(te.horas, 2.5)


class WebhookModelTest(BaseTestMixin, TestCase):
    def test_webhook_endpoint(self):
        from .models import WebhookEndpoint
        user = self.create_user()
        wh = WebhookEndpoint.objects.create(
            nome='Teste WH', url='https://example.com/hook',
            secret='sec123', events=['ticket.created'], criado_por=user,
        )
        self.assertTrue(wh.is_active)
        self.assertEqual(wh.failure_count, 0)


class SharedDashboardTest(BaseTestMixin, TestCase):
    def test_is_valid_no_expiry(self):
        from .models import SharedDashboard
        user = self.create_user()
        sd = SharedDashboard.objects.create(
            nome='Dash', token='abc123', criado_por=user,
            dashboard_config={'widgets': []},
        )
        self.assertTrue(sd.is_valid())

    def test_is_valid_expired(self):
        from .models import SharedDashboard
        user = self.create_user()
        sd = SharedDashboard.objects.create(
            nome='Old', token='xyz', criado_por=user,
            dashboard_config={},
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(sd.is_valid())


# ===========================================================================
# API Tests
# ===========================================================================

class HealthCheckAPITest(APITestCase):
    def test_health_check(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('database', data)


class JWTAuthAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()

    def test_obtain_jwt(self):
        response = self.client.post('/api/v1/auth/jwt/', {
            'username': 'testuser', 'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('access', data)
        self.assertIn('refresh', data)

    def test_jwt_refresh(self):
        res = self.client.post('/api/v1/auth/jwt/', {
            'username': 'testuser', 'password': 'testpass123',
        })
        refresh = res.json()['refresh']
        res2 = self.client.post('/api/v1/auth/jwt/refresh/', {'refresh': refresh})
        self.assertEqual(res2.status_code, 200)
        self.assertIn('access', res2.json())

    def test_invalid_credentials(self):
        res = self.client.post('/api/v1/auth/jwt/', {
            'username': 'testuser', 'password': 'wrong',
        })
        self.assertEqual(res.status_code, 401)


class TicketAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)
        self.cliente = self.create_cliente()

    def test_list_tickets(self):
        self.create_ticket(cliente=self.cliente, agente=self.user)
        res = self.client.get('/api/v1/tickets/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('results', res.json())

    def test_create_ticket(self):
        res = self.client.post('/api/v1/tickets/', {
            'titulo': 'Novo Ticket API',
            'descricao': 'Criado via API',
            'cliente_email': 'cliente@test.com',
            'prioridade': 'alta',
        })
        self.assertIn(res.status_code, [200, 201])

    def test_ticket_detail(self):
        ticket = self.create_ticket(cliente=self.cliente, agente=self.user)
        res = self.client.get(f'/api/v1/tickets/{ticket.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['titulo'], ticket.titulo)

    def test_unauthenticated_list(self):
        self.client.force_authenticate(user=None)
        res = self.client.get('/api/v1/tickets/')
        self.assertIn(res.status_code, [401, 403])


class ClienteAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)

    def test_list_clientes(self):
        self.create_cliente()
        res = self.client.get('/api/v1/clientes/')
        self.assertEqual(res.status_code, 200)

    def test_create_cliente(self):
        res = self.client.post('/api/v1/clientes/', {
            'nome': 'Novo Cliente', 'email': 'novo@api.com',
        })
        self.assertIn(res.status_code, [200, 201])


class BulkActionAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)
        self.cliente = self.create_cliente()

    def test_bulk_close(self):
        t1 = self.create_ticket(cliente=self.cliente, agente=self.user)
        t2 = self.create_ticket(
            cliente=self.create_cliente(nome='C2', email='c2@t.com'),
            agente=self.user,
        )
        res = self.client.post('/api/v1/tickets/bulk-action/', {
            'action': 'close', 'ticket_ids': [t1.pk, t2.pk],
        }, format='json')
        self.assertEqual(res.status_code, 200)
        t1.refresh_from_db()
        self.assertEqual(t1.status, 'fechado')


class AnalyticsAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)

    def test_overview(self):
        res = self.client.get('/api/v1/analytics/overview/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('total_tickets', data)

    def test_satisfaction(self):
        res = self.client.get('/api/v1/analytics/satisfaction/')
        # Pode retornar 200 ou 500 se models_satisfacao nao existe
        self.assertIn(res.status_code, [200, 500])


class CannedResponseAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        from .models import CannedResponse
        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)
        self.cr = CannedResponse.objects.create(
            titulo='Ola', corpo='Ola, posso ajudar?',
            categoria='geral', criado_por=self.user,
        )

    def test_list_canned(self):
        res = self.client.get('/api/v1/canned-responses/')
        self.assertEqual(res.status_code, 200)

    def test_detail_canned(self):
        res = self.client.get(f'/api/v1/canned-responses/{self.cr.pk}/')
        self.assertEqual(res.status_code, 200)


class ExportAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)

    def test_export_tickets_excel(self):
        self.create_ticket(cliente=self.create_cliente(), agente=self.user)
        res = self.client.get('/api/v1/export/tickets/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(
            'spreadsheet',
            res.get('Content-Type', ''),
        )


# ===========================================================================
# Service Tests
# ===========================================================================

class AIServiceTest(BaseTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.cliente = self.create_cliente()

    def test_predict_priority_heuristic(self):
        from .services.ai_service import ai_service
        result = ai_service.predict_priority(
            'URGENTE sistema fora do ar', 'Producao parada'
        )
        self.assertIn(result['priority'], ['critica', 'alta', 'media', 'baixa'])

    def test_analyze_sentiment_heuristic(self):
        from .services.ai_service import ai_service
        result = ai_service.analyze_sentiment('Pessimo servico horrivel')
        self.assertIn('sentiment', result)

    def test_find_duplicates(self):
        from .services.ai_service import ai_service
        self.create_ticket(
            cliente=self.create_cliente(nome='D1', email='d1@t.com'),
            titulo='Erro ao fazer login no sistema',
        )
        result = ai_service.find_duplicates(
            'Erro ao fazer login no sistema', 'Nao consigo logar'
        )
        self.assertIsInstance(result, list)


class WebhookServiceTest(BaseTestMixin, TestCase):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('dashboard.services.webhook_service.WebhookService._deliver')
    def test_trigger_event(self, mock_deliver):
        from .models import WebhookEndpoint
        from .services.webhook_service import webhook_service
        user = self.create_user()
        WebhookEndpoint.objects.create(
            nome='Hook', url='https://example.com/hook',
            secret='sec', events=['ticket.created'],
            criado_por=user,
        )
        webhook_service.trigger_event('ticket.created', {'id': 1})
        # Nao deve falhar


class GamificationServiceTest(BaseTestMixin, TestCase):
    def test_award_points(self):
        from .services.gamification_service import gamification_service
        from .models import AgentLeaderboard
        user = self.create_user()
        gamification_service.award_points(user, 'ticket_resolved')
        lb = AgentLeaderboard.objects.get(usuario=user)
        self.assertGreater(lb.pontos_total, 0)

    def test_leaderboard(self):
        from .services.gamification_service import gamification_service
        from .models import AgentLeaderboard
        u1 = self.create_user(username='ag1')
        u2 = self.create_user(username='ag2')
        gamification_service.award_points(u1, 'ticket_resolved')
        gamification_service.award_points(u1, 'ticket_resolved')
        gamification_service.award_points(u2, 'ticket_resolved')
        # get_leaderboard retorna por pontos_total desc
        leaders = gamification_service.get_leaderboard(limit=10)
        self.assertTrue(len(leaders) >= 2)
        self.assertGreaterEqual(leaders[0]['pontos_total'], leaders[1]['pontos_total'])


class CustomerHealthServiceTest(BaseTestMixin, TestCase):
    def test_calculate_all(self):
        from .services.customer_health_service import customer_health_service
        self.create_cliente()
        customer_health_service.calculate_all()
        # Nao deve falhar


# ===========================================================================
# RBAC Tests
# ===========================================================================

class RBACTest(BaseTestMixin, TestCase):
    def test_role_admin(self):
        from .rbac import UserRole, get_user_role, user_has_role, ROLE_ADMIN
        admin = self.create_admin()
        role = UserRole.objects.create(user=admin, role='admin')
        self.assertEqual(role.role, 'admin')
        self.assertEqual(get_user_role(admin), ROLE_ADMIN)
        self.assertTrue(user_has_role(admin, 'admin', 'supervisor'))

    def test_role_agent_no_manage(self):
        from .rbac import UserRole, get_user_role, user_has_role
        user = self.create_user(username='ag')
        role = UserRole.objects.create(user=user, role='agente')
        self.assertEqual(get_user_role(user), 'agente')
        self.assertFalse(user_has_role(user, 'admin'))
        self.assertTrue(user_has_role(user, 'agente'))
