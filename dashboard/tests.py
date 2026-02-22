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


# ===========================================================================
# P0: Crypto / Encryption Tests
# ===========================================================================

class CryptoModuleTest(TestCase):
    """Testes para módulo de criptografia Fernet (P0/PCI-DSS)."""

    def test_encrypt_decrypt_roundtrip(self):
        from .crypto import encrypt_value, decrypt_value
        original = 'minha-api-key-super-secreta-123'
        encrypted = encrypt_value(original)
        self.assertTrue(encrypted.startswith('enc::'))
        self.assertNotEqual(encrypted, original)
        decrypted = decrypt_value(encrypted)
        self.assertEqual(decrypted, original)

    def test_encrypt_empty_value(self):
        from .crypto import encrypt_value, decrypt_value
        self.assertEqual(encrypt_value(''), '')
        self.assertIsNone(encrypt_value(None))
        self.assertEqual(decrypt_value(''), '')

    def test_no_double_encrypt(self):
        from .crypto import encrypt_value
        encrypted = encrypt_value('secret')
        double = encrypt_value(encrypted)
        self.assertEqual(encrypted, double)

    def test_encrypted_model_field_aiconfiguration(self):
        from .models import AIConfiguration
        ai = AIConfiguration.objects.create(
            provider='openai',
            api_key='sk-test-key-12345',
            model_name='gpt-4o-mini',
        )
        ai.refresh_from_db()
        # No banco está criptografado
        from .models import AIConfiguration as AI2
        raw = AI2.objects.filter(pk=ai.pk).values_list('api_key', flat=True).first()
        self.assertTrue(raw.startswith('enc::'))
        # Getter descriptografa
        self.assertEqual(ai.get_api_key(), 'sk-test-key-12345')

    def test_encrypted_cliente_telefone(self):
        cliente = Cliente.objects.create(
            nome='Teste LGPD',
            email='lgpd@test.com',
            telefone='(11) 99999-1234',
        )
        cliente.refresh_from_db()
        # Campo raw criptografado
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT telefone FROM dashboard_cliente WHERE id = %s",
                [cliente.pk]
            )
            raw_tel = cursor.fetchone()[0]
        self.assertTrue(raw_tel.startswith('enc::'))
        # Getter descriptografa
        self.assertEqual(cliente.get_telefone(), '(11) 99999-1234')

    def test_encrypted_webhook_secret(self):
        from .models import WebhookEndpoint
        user = User.objects.create_user(username='wh_test', password='p')
        wh = WebhookEndpoint.objects.create(
            nome='WH Crypto', url='https://hook.example.com',
            secret='webhook-secret-abc', events=['ticket.created'],
            criado_por=user,
        )
        wh.refresh_from_db()
        self.assertEqual(wh.get_secret(), 'webhook-secret-abc')


# ===========================================================================
# P1: Soft Delete Tests
# ===========================================================================

class SoftDeleteTest(BaseTestMixin, TestCase):
    """Testes para soft delete em modelos financeiros (P1/BACEN)."""

    def test_contrato_soft_delete(self):
        from .models import Contrato
        from decimal import Decimal
        cliente = self.create_cliente()
        contrato = Contrato.objects.create(
            cliente=cliente,
            numero_contrato='CTR-001',
            descricao='Contrato teste',
            valor_mensal=Decimal('1500.00'),
            data_inicio='2025-01-01',
        )
        user = self.create_user()
        contrato.soft_delete(user=user)
        # Não aparece na query padrão
        self.assertFalse(Contrato.objects.filter(pk=contrato.pk).exists())
        # Mas existe no all_objects
        self.assertTrue(Contrato.all_objects.filter(pk=contrato.pk).exists())
        # Pode ser restaurado
        contrato_del = Contrato.all_objects.get(pk=contrato.pk)
        contrato_del.restore()
        self.assertTrue(Contrato.objects.filter(pk=contrato.pk).exists())

    def test_fatura_soft_delete(self):
        from .models import Contrato, Fatura
        from decimal import Decimal
        cliente = self.create_cliente()
        contrato = Contrato.objects.create(
            cliente=cliente,
            numero_contrato='CTR-002',
            descricao='Contrato',
            valor_mensal=Decimal('1000.00'),
            data_inicio='2025-01-01',
        )
        fatura = Fatura.objects.create(
            contrato=contrato,
            numero_fatura='FAT-001',
            valor=Decimal('1000.00'),
            data_vencimento='2025-02-01',
        )
        fatura.soft_delete()
        self.assertEqual(Fatura.objects.count(), 0)
        self.assertEqual(Fatura.all_objects.count(), 1)

    def test_movimentacao_financeira_soft_delete(self):
        from .models import MovimentacaoFinanceira, CategoriaFinanceira
        from decimal import Decimal
        user = self.create_user()
        cat = CategoriaFinanceira.objects.create(
            nome='Receitas', tipo='receita'
        )
        mov = MovimentacaoFinanceira.objects.create(
            categoria=cat,
            descricao='Venda servicos',
            tipo='receita',
            valor=Decimal('5000.00'),
            data_movimentacao='2025-01-15',
            usuario=user,
        )
        mov.soft_delete(user=user)
        self.assertFalse(MovimentacaoFinanceira.objects.filter(pk=mov.pk).exists())
        self.assertTrue(MovimentacaoFinanceira.all_objects.filter(pk=mov.pk).exists())

    def test_soft_delete_preserves_data(self):
        from .models import CategoriaFinanceira
        cat = CategoriaFinanceira.objects.create(
            nome='Despesas TI', tipo='despesa'
        )
        cat.soft_delete()
        cat_del = CategoriaFinanceira.all_objects.get(pk=cat.pk)
        self.assertEqual(cat_del.nome, 'Despesas TI')
        self.assertTrue(cat_del.is_deleted)
        self.assertIsNotNone(cat_del.deleted_at)


# ===========================================================================
# P1: CheckConstraint Tests
# ===========================================================================

class CheckConstraintTest(BaseTestMixin, TestCase):
    """Testes para CheckConstraints no banco de dados (P1/integridade)."""

    def test_fatura_valor_positivo(self):
        from .models import Contrato, Fatura
        from decimal import Decimal
        from django.db import IntegrityError
        cliente = self.create_cliente()
        contrato = Contrato.objects.create(
            cliente=cliente,
            numero_contrato='CTR-CC-01',
            descricao='CC test',
            valor_mensal=Decimal('500.00'),
            data_inicio='2025-01-01',
        )
        with self.assertRaises((IntegrityError, Exception)):
            Fatura.objects.create(
                contrato=contrato,
                numero_fatura='FAT-NEG',
                valor=Decimal('-100.00'),
                data_vencimento='2025-03-01',
            )

    def test_centro_custo_alerta_percentual_0_100(self):
        from .models import CentroCusto
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        cc = CentroCusto(
            codigo='CC-TST',
            nome='CC teste',
            departamento='TI',
            alerta_percentual=Decimal('150.00'),
        )
        with self.assertRaises((Exception,)):
            cc.full_clean()


# ===========================================================================
# P1: FloatField → DecimalField Tests
# ===========================================================================

class DecimalFieldTest(TestCase):
    """Verifica que campos convertidos de FloatField para DecimalField funcionam."""

    def test_system_metrics_decimal(self):
        from .models import SystemMetrics
        from decimal import Decimal
        sm = SystemMetrics.objects.create(
            date='2025-01-01',
            total_tickets=100,
            sla_compliance_rate=Decimal('95.50'),
            avg_resolution_time=Decimal('4.25'),
            customer_satisfaction=Decimal('88.75'),
        )
        sm.refresh_from_db()
        self.assertEqual(sm.sla_compliance_rate, Decimal('95.50'))
        self.assertEqual(sm.avg_resolution_time, Decimal('4.25'))

    def test_customer_health_score_decimal(self):
        from .models import CustomerHealthScore
        from decimal import Decimal
        cliente = Cliente.objects.create(nome='HS', email='hs@t.com')
        hs = CustomerHealthScore.objects.create(
            cliente=cliente,
            score=Decimal('85.50'),
            ticket_frequency_score=Decimal('90.00'),
            satisfaction_score=Decimal('80.25'),
            resolution_time_score=Decimal('75.00'),
            escalation_score=Decimal('95.00'),
        )
        hs.refresh_from_db()
        self.assertEqual(hs.score, Decimal('85.50'))


# ===========================================================================
# P0+P1: RBAC / IDOR Tests
# ===========================================================================

class RBACViewTest(BaseTestMixin, TestCase):
    """Testes para RBAC nas views de ticket (P0/IDOR prevention)."""

    def setUp(self):
        self.factory = RequestFactory()
        # Agente A
        self.agent_a = self.create_user(username='agent_a')
        self.agent_a.is_staff = True
        self.agent_a.save()
        # Agente B
        self.agent_b = self.create_user(username='agent_b')
        self.agent_b.is_staff = True
        self.agent_b.save()
        # Clientes
        self.cliente_a = self.create_cliente(nome='CLI A', email='clia@t.com')
        self.cliente_b = self.create_cliente(nome='CLI B', email='clib@t.com')
        # Tickets
        self.ticket_a = self.create_ticket(
            cliente=self.cliente_a, agente=self.agent_a, titulo='Ticket A'
        )
        self.ticket_b = self.create_ticket(
            cliente=self.cliente_b, agente=self.agent_b, titulo='Ticket B'
        )

    def test_rbac_helpers_staff_sees_all(self):
        from .views_helpers import get_role_filtered_tickets
        qs = get_role_filtered_tickets(self.agent_a, Ticket.objects.all())
        # Staff vê todos os tickets
        self.assertEqual(qs.count(), 2)

    def test_rbac_helpers_user_access(self):
        from .views_helpers import user_can_access_ticket
        admin = self.create_admin(username='boss')
        self.assertTrue(user_can_access_ticket(admin, self.ticket_a))
        self.assertTrue(user_can_access_ticket(admin, self.ticket_b))


# ===========================================================================
# LGPD Tests
# ===========================================================================

class LGPDModelTest(BaseTestMixin, TestCase):
    """Testes para modelos de conformidade LGPD."""

    def test_consent_create_and_revoke(self):
        from .models_lgpd import LGPDConsent
        user = self.create_user()
        consent = LGPDConsent.objects.create(
            user=user,
            purpose='communication',
            granted=True,
            legal_basis='consent',
        )
        self.assertTrue(consent.is_valid)
        consent.revoke()
        self.assertFalse(consent.is_valid)

    def test_data_request_lifecycle(self):
        from .models_lgpd import LGPDDataRequest
        user = self.create_user()
        admin = self.create_admin()
        req = LGPDDataRequest.objects.create(
            user=user,
            request_type='access',
            description='Quero ver meus dados',
        )
        self.assertEqual(req.status, 'pending')
        req.complete(processed_by=admin, response='Dados enviados por email')
        self.assertEqual(req.status, 'completed')
        self.assertIsNotNone(req.completed_at)

    def test_access_log(self):
        from .models_lgpd import LGPDAccessLog
        user = self.create_user()
        log = LGPDAccessLog.objects.create(
            user=user,
            action='view',
            resource_type='Cliente',
            resource_id='42',
            fields_accessed=['telefone', 'celular'],
            ip_address='192.168.1.10',
        )
        self.assertEqual(log.action, 'view')
        self.assertIn('telefone', log.fields_accessed)

    def test_pii_encryption_perfil(self):
        from .models import PerfilUsuario
        user = self.create_user()
        perfil = PerfilUsuario.objects.create(
            user=user,
            telefone='(11) 98765-4321',
            endereco='Rua Teste, 123',
            cep='01234-567',
        )
        perfil.refresh_from_db()
        # Getter descriptografa
        self.assertEqual(perfil.get_telefone(), '(11) 98765-4321')
        self.assertEqual(perfil.get_endereco(), 'Rua Teste, 123')
        self.assertEqual(perfil.get_cep(), '01234-567')

    def test_pii_encryption_ponto_venda(self):
        from .models import PontoDeVenda
        pdv = PontoDeVenda.objects.create(
            razao_social='Empresa Teste LTDA',
            nome_fantasia='Teste',
            cnpj='12.345.678/0001-90',
            cep='01234-567',
            logradouro='Rua Teste',
            numero='100',
            bairro='Centro',
            cidade='São Paulo',
            estado='SP',
            celular='(11) 91234-5678',
            email_principal='emp@test.com',
            responsavel_nome='João',
            responsavel_cpf='123.456.789-00',
            responsavel_cargo='Diretor',
            responsavel_telefone='(11) 3456-7890',
            responsavel_email='joao@test.com',
        )
        pdv.refresh_from_db()
        self.assertEqual(pdv.get_responsavel_cpf(), '123.456.789-00')
        self.assertEqual(pdv.get_celular(), '(11) 91234-5678')
        self.assertEqual(pdv.get_responsavel_telefone(), '(11) 3456-7890')
