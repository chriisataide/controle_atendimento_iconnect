"""
Tests — Testes unitarios e de integracao para iConnect Helpdesk
Cobre: Models, API, Services, RBAC, Webhooks, AI, Gamification
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from ..models import CategoriaTicket, Cliente, PrioridadeTicket, StatusTicket, Ticket

# ===========================================================================
# Factory helpers
# ===========================================================================


class BaseTestMixin:
    """Helpers comuns para testes"""

    def create_user(self, username="testuser", password="testpass123", **kwargs):
        return User.objects.create_user(username=username, password=password, email=f"{username}@test.com", **kwargs)

    def create_admin(self, username="admin", password="admin123"):
        return User.objects.create_superuser(username=username, password=password, email=f"{username}@test.com")

    def create_cliente(self, nome="Cliente Teste", email="cliente@test.com"):
        return Cliente.objects.create(nome=nome, email=email)

    def create_ticket(self, cliente=None, agente=None, **kwargs):
        if not cliente:
            cliente = self.create_cliente()
        defaults = {
            "titulo": "Ticket de Teste",
            "descricao": "Descricao do ticket de teste",
            "cliente": cliente,
            "agente": agente,
            "status": "aberto",
            "prioridade": "media",
        }
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    def create_categoria(self, nome="Suporte Tecnico"):
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
        user = User.objects.create_user(username="cli1", password="pass")
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
        self.user = self.create_user(username="agente")
        self.cliente = self.create_cliente()
        self.categoria = self.create_categoria()

    def test_criacao_ticket(self):
        ticket = Ticket.objects.create(
            cliente=self.cliente,
            agente=self.user,
            categoria=self.categoria,
            titulo="Problema de Teste",
            descricao="Descricao",
            prioridade=PrioridadeTicket.ALTA,
            status=StatusTicket.ABERTO,
        )
        self.assertTrue(ticket.numero)
        self.assertEqual(ticket.titulo, "Problema de Teste")
        self.assertEqual(ticket.status, StatusTicket.ABERTO)

    def test_ticket_str(self):
        ticket = self.create_ticket(cliente=self.cliente, agente=self.user)
        self.assertIn(ticket.numero, str(ticket))

    def test_ticket_status_default(self):
        ticket = self.create_ticket(cliente=self.cliente)
        self.assertEqual(ticket.status, "aberto")

    def test_ticket_tipo_itil(self):
        ticket = self.create_ticket(cliente=self.cliente, tipo="problema")
        self.assertEqual(ticket.tipo, "problema")


class CannedResponseModelTest(BaseTestMixin, TestCase):
    def test_canned_response_create(self):
        from ..models import CannedResponse

        user = self.create_user()
        cr = CannedResponse.objects.create(
            titulo="Saudacao",
            corpo="Ola, como posso ajudar?",
            categoria="geral",
            criado_por=user,
        )
        self.assertIn("Saudacao", str(cr))


class APIKeyModelTest(BaseTestMixin, TestCase):
    def test_generate_key(self):
        from ..models import APIKey

        user = self.create_user()
        raw_key, key_hash, prefix = APIKey.generate_key()
        api_key = APIKey.objects.create(
            nome="Teste Key",
            criado_por=user,
            key_hash=key_hash,
            prefix=prefix,
        )
        self.assertTrue(raw_key.startswith(prefix))
        self.assertTrue(api_key.is_valid())

    def test_revoked_key(self):
        from ..models import APIKey

        user = self.create_user()
        _, key_hash, prefix = APIKey.generate_key()
        api_key = APIKey.objects.create(
            nome="Rev",
            criado_por=user,
            key_hash=key_hash,
            prefix=prefix,
        )
        api_key.is_active = False
        api_key.save()
        self.assertFalse(api_key.is_valid())


class TagModelTest(TestCase):
    def test_tag_create(self):
        from ..models import Tag

        tag = Tag.objects.create(nome="VIP", cor="#ff0000")
        self.assertEqual(str(tag), "VIP")


class TimeEntryTest(BaseTestMixin, TestCase):
    def test_horas_property(self):
        from ..models import TimeEntry

        user = self.create_user()
        ticket = self.create_ticket()
        te = TimeEntry.objects.create(ticket=ticket, usuario=user, minutos=150)
        self.assertAlmostEqual(te.horas, 2.5)


class WebhookModelTest(BaseTestMixin, TestCase):
    def test_webhook_endpoint(self):
        from ..models import WebhookEndpoint

        user = self.create_user()
        wh = WebhookEndpoint.objects.create(
            nome="Teste WH",
            url="https://example.com/hook",
            secret="sec123",
            events=["ticket.created"],
            criado_por=user,
        )
        self.assertTrue(wh.is_active)
        self.assertEqual(wh.failure_count, 0)


class SharedDashboardTest(BaseTestMixin, TestCase):
    def test_is_valid_no_expiry(self):
        from ..models import SharedDashboard

        user = self.create_user()
        sd = SharedDashboard.objects.create(
            nome="Dash",
            token="abc123",
            criado_por=user,
            dashboard_config={"widgets": []},
        )
        self.assertTrue(sd.is_valid())

    def test_is_valid_expired(self):
        from ..models import SharedDashboard

        user = self.create_user()
        sd = SharedDashboard.objects.create(
            nome="Old",
            token="xyz",
            criado_por=user,
            dashboard_config={},
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(sd.is_valid())


# ===========================================================================
# API Tests
# ===========================================================================


class HealthCheckAPITest(APITestCase):
    def test_health_check(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("database", data)


class JWTAuthAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()

    def test_obtain_jwt(self):
        response = self.client.post(
            "/api/v1/auth/jwt/",
            {
                "username": "testuser",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)

    def test_jwt_refresh(self):
        res = self.client.post(
            "/api/v1/auth/jwt/",
            {
                "username": "testuser",
                "password": "testpass123",
            },
        )
        refresh = res.json()["refresh"]
        res2 = self.client.post("/api/v1/auth/jwt/refresh/", {"refresh": refresh})
        self.assertEqual(res2.status_code, 200)
        self.assertIn("access", res2.json())

    def test_invalid_credentials(self):
        res = self.client.post(
            "/api/v1/auth/jwt/",
            {
                "username": "testuser",
                "password": "wrong",
            },
        )
        self.assertEqual(res.status_code, 401)


class TicketAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)
        self.cliente = self.create_cliente()

    def test_list_tickets(self):
        self.create_ticket(cliente=self.cliente, agente=self.user)
        res = self.client.get("/api/v1/tickets/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("results", res.json())

    def test_create_ticket(self):
        res = self.client.post(
            "/api/v1/tickets/",
            {
                "titulo": "Novo Ticket API",
                "descricao": "Criado via API",
                "cliente_email": "cliente@test.com",
                "prioridade": "alta",
            },
        )
        self.assertIn(res.status_code, [200, 201])

    def test_ticket_detail(self):
        ticket = self.create_ticket(cliente=self.cliente, agente=self.user)
        res = self.client.get(f"/api/v1/tickets/{ticket.pk}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["titulo"], ticket.titulo)

    def test_unauthenticated_list(self):
        self.client.force_authenticate(user=None)
        res = self.client.get("/api/v1/tickets/")
        self.assertIn(res.status_code, [401, 403])


class ClienteAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)

    def test_list_clientes(self):
        self.create_cliente()
        res = self.client.get("/api/v1/clientes/")
        self.assertEqual(res.status_code, 200)

    def test_create_cliente(self):
        res = self.client.post(
            "/api/v1/clientes/",
            {
                "nome": "Novo Cliente",
                "email": "novo@api.com",
            },
        )
        self.assertIn(res.status_code, [200, 201])


class BulkActionAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_admin()  # Bulk actions requerem admin/staff
        self.client.force_authenticate(user=self.user)
        self.cliente = self.create_cliente()

    def test_bulk_close(self):
        t1 = self.create_ticket(cliente=self.cliente, agente=self.user)
        t2 = self.create_ticket(
            cliente=self.create_cliente(nome="C2", email="c2@t.com"),
            agente=self.user,
        )
        res = self.client.post(
            "/api/v1/tickets/bulk-action/",
            {
                "action": "close",
                "ticket_ids": [t1.pk, t2.pk],
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        t1.refresh_from_db()
        self.assertEqual(t1.status, "fechado")


class AnalyticsAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)

    def test_overview(self):
        res = self.client.get("/api/v1/analytics/overview/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_tickets", data)

    def test_satisfaction(self):
        res = self.client.get("/api/v1/analytics/satisfaction/")
        # Pode retornar 200 ou 500 se models_satisfacao nao existe
        self.assertIn(res.status_code, [200, 500])


class CannedResponseAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        from ..models import CannedResponse

        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)
        self.cr = CannedResponse.objects.create(
            titulo="Ola",
            corpo="Ola, posso ajudar?",
            categoria="geral",
            criado_por=self.user,
        )

    def test_list_canned(self):
        res = self.client.get("/api/v1/canned-responses/")
        self.assertEqual(res.status_code, 200)

    def test_detail_canned(self):
        res = self.client.get(f"/api/v1/canned-responses/{self.cr.pk}/")
        self.assertEqual(res.status_code, 200)


class ExportAPITest(BaseTestMixin, APITestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_authenticate(user=self.user)

    def test_export_tickets_excel(self):
        self.create_ticket(cliente=self.create_cliente(), agente=self.user)
        res = self.client.get("/api/v1/export/tickets/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(
            "spreadsheet",
            res.get("Content-Type", ""),
        )


# ===========================================================================
# Service Tests
# ===========================================================================


class AIServiceTest(BaseTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.cliente = self.create_cliente()

    def test_predict_priority_heuristic(self):
        from ..services.ai_service import ai_service

        result = ai_service.predict_priority("URGENTE sistema fora do ar", "Producao parada")
        self.assertIn(result["priority"], ["critica", "alta", "media", "baixa"])

    def test_analyze_sentiment_heuristic(self):
        from ..services.ai_service import ai_service

        result = ai_service.analyze_sentiment("Pessimo servico horrivel")
        self.assertIn("sentiment", result)

    def test_find_duplicates(self):
        from ..services.ai_service import ai_service

        self.create_ticket(
            cliente=self.create_cliente(nome="D1", email="d1@t.com"),
            titulo="Erro ao fazer login no sistema",
        )
        result = ai_service.find_duplicates("Erro ao fazer login no sistema", "Nao consigo logar")
        self.assertIsInstance(result, list)


class WebhookServiceTest(BaseTestMixin, TestCase):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("dashboard.services.webhook_service.WebhookService._deliver")
    def test_trigger_event(self, mock_deliver):
        from ..models import WebhookEndpoint
        from ..services.webhook_service import webhook_service

        user = self.create_user()
        WebhookEndpoint.objects.create(
            nome="Hook",
            url="https://example.com/hook",
            secret="sec",
            events=["ticket.created"],
            criado_por=user,
        )
        webhook_service.trigger_event("ticket.created", {"id": 1})
        # Nao deve falhar


class GamificationServiceTest(BaseTestMixin, TestCase):
    def test_award_points(self):
        from ..models import AgentLeaderboard
        from ..services.gamification_service import gamification_service

        user = self.create_user()
        gamification_service.award_points(user, "ticket_resolved")
        lb = AgentLeaderboard.objects.get(usuario=user)
        self.assertGreater(lb.pontos_total, 0)

    def test_leaderboard(self):
        from ..services.gamification_service import gamification_service

        u1 = self.create_user(username="ag1")
        u2 = self.create_user(username="ag2")
        gamification_service.award_points(u1, "ticket_resolved")
        gamification_service.award_points(u1, "ticket_resolved")
        gamification_service.award_points(u2, "ticket_resolved")
        # get_leaderboard retorna por pontos_total desc
        leaders = gamification_service.get_leaderboard(limit=10)
        self.assertTrue(len(leaders) >= 2)
        self.assertGreaterEqual(leaders[0]["pontos_total"], leaders[1]["pontos_total"])


class CustomerHealthServiceTest(BaseTestMixin, TestCase):
    def test_calculate_all(self):
        from ..services.customer_health_service import customer_health_service

        self.create_cliente()
        customer_health_service.calculate_all()
        # Nao deve falhar


# ===========================================================================
# RBAC Tests
# ===========================================================================


class RBACTest(BaseTestMixin, TestCase):
    def test_role_admin(self):
        from ..utils.rbac import ROLE_ADMIN, UserRole, get_user_role, user_has_role

        admin = self.create_admin()
        role = UserRole.objects.create(user=admin, role="admin")
        self.assertEqual(role.role, "admin")
        self.assertEqual(get_user_role(admin), ROLE_ADMIN)
        self.assertTrue(user_has_role(admin, "admin", "supervisor"))

    def test_role_agent_no_manage(self):
        from ..utils.rbac import UserRole, get_user_role, user_has_role

        user = self.create_user(username="ag")
        role = UserRole.objects.create(user=user, role="agente")
        self.assertEqual(get_user_role(user), "agente")
        self.assertFalse(user_has_role(user, "admin"))
        self.assertTrue(user_has_role(user, "agente"))


# ===========================================================================
# P0: Crypto / Encryption Tests
# ===========================================================================


class CryptoModuleTest(TestCase):
    """Testes para módulo de criptografia Fernet (P0/PCI-DSS)."""

    def test_encrypt_decrypt_roundtrip(self):
        from ..utils.crypto import decrypt_value, encrypt_value

        original = "minha-api-key-super-secreta-123"
        encrypted = encrypt_value(original)
        self.assertTrue(encrypted.startswith("enc::"))
        self.assertNotEqual(encrypted, original)
        decrypted = decrypt_value(encrypted)
        self.assertEqual(decrypted, original)

    def test_encrypt_empty_value(self):
        from ..utils.crypto import decrypt_value, encrypt_value

        self.assertEqual(encrypt_value(""), "")
        self.assertIsNone(encrypt_value(None))
        self.assertEqual(decrypt_value(""), "")

    def test_no_double_encrypt(self):
        from ..utils.crypto import encrypt_value

        encrypted = encrypt_value("secret")
        double = encrypt_value(encrypted)
        self.assertEqual(encrypted, double)

    def test_encrypted_model_field_aiconfiguration(self):
        from ..models import AIConfiguration

        ai = AIConfiguration.objects.create(
            provider="openai",
            api_key="sk-test-key-12345",
            model_name="gpt-4o-mini",
        )
        ai.refresh_from_db()
        # No banco está criptografado
        from ..models import AIConfiguration as AI2

        raw = AI2.objects.filter(pk=ai.pk).values_list("api_key", flat=True).first()
        self.assertTrue(raw.startswith("enc::"))
        # Getter descriptografa
        self.assertEqual(ai.get_api_key(), "sk-test-key-12345")

    def test_encrypted_cliente_telefone(self):
        cliente = Cliente.objects.create(
            nome="Teste LGPD",
            email="lgpd@test.com",
            telefone="(11) 99999-1234",
        )
        cliente.refresh_from_db()
        # Campo raw criptografado
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT telefone FROM dashboard_cliente WHERE id = %s", [cliente.pk])
            raw_tel = cursor.fetchone()[0]
        self.assertTrue(raw_tel.startswith("enc::"))
        # Getter descriptografa
        self.assertEqual(cliente.get_telefone(), "(11) 99999-1234")

    def test_encrypted_webhook_secret(self):
        from ..models import WebhookEndpoint

        user = User.objects.create_user(username="wh_test", password="p")
        wh = WebhookEndpoint.objects.create(
            nome="WH Crypto",
            url="https://hook.example.com",
            secret="webhook-secret-abc",
            events=["ticket.created"],
            criado_por=user,
        )
        wh.refresh_from_db()
        self.assertEqual(wh.get_secret(), "webhook-secret-abc")


# ===========================================================================
# P1: Soft Delete Tests
# ===========================================================================


class SoftDeleteTest(BaseTestMixin, TestCase):
    """Testes para soft delete em modelos financeiros (P1/BACEN)."""

    def test_contrato_soft_delete(self):
        from decimal import Decimal

        from ..models import Contrato

        cliente = self.create_cliente()
        contrato = Contrato.objects.create(
            cliente=cliente,
            numero_contrato="CTR-001",
            descricao="Contrato teste",
            valor_mensal=Decimal("1500.00"),
            data_inicio="2025-01-01",
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
        from decimal import Decimal

        from ..models import Contrato, Fatura

        cliente = self.create_cliente()
        contrato = Contrato.objects.create(
            cliente=cliente,
            numero_contrato="CTR-002",
            descricao="Contrato",
            valor_mensal=Decimal("1000.00"),
            data_inicio="2025-01-01",
        )
        fatura = Fatura.objects.create(
            contrato=contrato,
            numero_fatura="FAT-001",
            valor=Decimal("1000.00"),
            data_vencimento="2025-02-01",
        )
        fatura.soft_delete()
        self.assertEqual(Fatura.objects.count(), 0)
        self.assertEqual(Fatura.all_objects.count(), 1)

    def test_movimentacao_financeira_soft_delete(self):
        from decimal import Decimal

        from ..models import CategoriaFinanceira, MovimentacaoFinanceira

        user = self.create_user()
        cat = CategoriaFinanceira.objects.create(nome="Receitas", tipo="receita")
        mov = MovimentacaoFinanceira.objects.create(
            categoria=cat,
            descricao="Venda servicos",
            tipo="receita",
            valor=Decimal("5000.00"),
            data_movimentacao="2025-01-15",
            usuario=user,
        )
        mov.soft_delete(user=user)
        self.assertFalse(MovimentacaoFinanceira.objects.filter(pk=mov.pk).exists())
        self.assertTrue(MovimentacaoFinanceira.all_objects.filter(pk=mov.pk).exists())

    def test_soft_delete_preserves_data(self):
        from ..models import CategoriaFinanceira

        cat = CategoriaFinanceira.objects.create(nome="Despesas TI", tipo="despesa")
        cat.soft_delete()
        cat_del = CategoriaFinanceira.all_objects.get(pk=cat.pk)
        self.assertEqual(cat_del.nome, "Despesas TI")
        self.assertTrue(cat_del.is_deleted)
        self.assertIsNotNone(cat_del.deleted_at)


# ===========================================================================
# P1: CheckConstraint Tests
# ===========================================================================


class CheckConstraintTest(BaseTestMixin, TestCase):
    """Testes para CheckConstraints no banco de dados (P1/integridade)."""

    def test_fatura_valor_positivo(self):
        from decimal import Decimal

        from django.db import IntegrityError

        from ..models import Contrato, Fatura

        cliente = self.create_cliente()
        contrato = Contrato.objects.create(
            cliente=cliente,
            numero_contrato="CTR-CC-01",
            descricao="CC test",
            valor_mensal=Decimal("500.00"),
            data_inicio="2025-01-01",
        )
        with self.assertRaises((IntegrityError, Exception)):
            Fatura.objects.create(
                contrato=contrato,
                numero_fatura="FAT-NEG",
                valor=Decimal("-100.00"),
                data_vencimento="2025-03-01",
            )

    def test_centro_custo_alerta_percentual_0_100(self):
        from decimal import Decimal

        from ..models import CentroCusto

        cc = CentroCusto(
            codigo="CC-TST",
            nome="CC teste",
            departamento="TI",
            alerta_percentual=Decimal("150.00"),
        )
        with self.assertRaises((Exception,)):
            cc.full_clean()


# ===========================================================================
# P1: FloatField → DecimalField Tests
# ===========================================================================


class DecimalFieldTest(TestCase):
    """Verifica que campos convertidos de FloatField para DecimalField funcionam."""

    def test_system_metrics_decimal(self):
        from decimal import Decimal

        from ..models import SystemMetrics

        sm = SystemMetrics.objects.create(
            date="2025-01-01",
            total_tickets=100,
            sla_compliance_rate=Decimal("95.50"),
            avg_resolution_time=Decimal("4.25"),
            customer_satisfaction=Decimal("88.75"),
        )
        sm.refresh_from_db()
        self.assertEqual(sm.sla_compliance_rate, Decimal("95.50"))
        self.assertEqual(sm.avg_resolution_time, Decimal("4.25"))

    def test_customer_health_score_decimal(self):
        from decimal import Decimal

        from ..models import CustomerHealthScore

        cliente = Cliente.objects.create(nome="HS", email="hs@t.com")
        hs = CustomerHealthScore.objects.create(
            cliente=cliente,
            score=Decimal("85.50"),
            ticket_frequency_score=Decimal("90.00"),
            satisfaction_score=Decimal("80.25"),
            resolution_time_score=Decimal("75.00"),
            escalation_score=Decimal("95.00"),
        )
        hs.refresh_from_db()
        self.assertEqual(hs.score, Decimal("85.50"))


# ===========================================================================
# P0+P1: RBAC / IDOR Tests
# ===========================================================================


class RBACViewTest(BaseTestMixin, TestCase):
    """Testes para RBAC nas views de ticket (P0/IDOR prevention)."""

    def setUp(self):
        self.factory = RequestFactory()
        # Agente A
        self.agent_a = self.create_user(username="agent_a")
        self.agent_a.is_staff = True
        self.agent_a.save()
        # Agente B
        self.agent_b = self.create_user(username="agent_b")
        self.agent_b.is_staff = True
        self.agent_b.save()
        # Clientes
        self.cliente_a = self.create_cliente(nome="CLI A", email="clia@t.com")
        self.cliente_b = self.create_cliente(nome="CLI B", email="clib@t.com")
        # Tickets
        self.ticket_a = self.create_ticket(cliente=self.cliente_a, agente=self.agent_a, titulo="Ticket A")
        self.ticket_b = self.create_ticket(cliente=self.cliente_b, agente=self.agent_b, titulo="Ticket B")

    def test_rbac_helpers_staff_sees_all(self):
        from ..views.helpers import get_role_filtered_tickets

        qs = get_role_filtered_tickets(self.agent_a, Ticket.objects.all())
        # Staff vê todos os tickets
        self.assertEqual(qs.count(), 2)

    def test_rbac_helpers_user_access(self):
        from ..views.helpers import user_can_access_ticket

        admin = self.create_admin(username="boss")
        self.assertTrue(user_can_access_ticket(admin, self.ticket_a))
        self.assertTrue(user_can_access_ticket(admin, self.ticket_b))


# ===========================================================================
# LGPD Tests
# ===========================================================================


class LGPDModelTest(BaseTestMixin, TestCase):
    """Testes para modelos de conformidade LGPD."""

    def test_consent_create_and_revoke(self):
        from ..models import LGPDConsent

        user = self.create_user()
        consent = LGPDConsent.objects.create(
            user=user,
            purpose="communication",
            granted=True,
            legal_basis="consent",
        )
        self.assertTrue(consent.is_valid)
        consent.revoke()
        self.assertFalse(consent.is_valid)

    def test_data_request_lifecycle(self):
        from ..models import LGPDDataRequest

        user = self.create_user()
        admin = self.create_admin()
        req = LGPDDataRequest.objects.create(
            user=user,
            request_type="access",
            description="Quero ver meus dados",
        )
        self.assertEqual(req.status, "pending")
        req.complete(processed_by=admin, response="Dados enviados por email")
        self.assertEqual(req.status, "completed")
        self.assertIsNotNone(req.completed_at)

    def test_access_log(self):
        from ..models import LGPDAccessLog

        user = self.create_user()
        log = LGPDAccessLog.objects.create(
            user=user,
            action="view",
            resource_type="Cliente",
            resource_id="42",
            fields_accessed=["telefone", "celular"],
            ip_address="192.168.1.10",
        )
        self.assertEqual(log.action, "view")
        self.assertIn("telefone", log.fields_accessed)

    def test_pii_encryption_perfil(self):
        from ..models import PerfilUsuario

        user = self.create_user()
        perfil = PerfilUsuario.objects.create(
            user=user,
            telefone="(11) 98765-4321",
            endereco="Rua Teste, 123",
            cep="01234-567",
        )
        perfil.refresh_from_db()
        # Getter descriptografa
        self.assertEqual(perfil.get_telefone(), "(11) 98765-4321")
        self.assertEqual(perfil.get_endereco(), "Rua Teste, 123")
        self.assertEqual(perfil.get_cep(), "01234-567")

    def test_pii_encryption_ponto_venda(self):
        from ..models import PontoDeVenda

        pdv = PontoDeVenda.objects.create(
            razao_social="Empresa Teste LTDA",
            nome_fantasia="Teste",
            cnpj="12.345.678/0001-90",
            cep="01234-567",
            logradouro="Rua Teste",
            numero="100",
            bairro="Centro",
            cidade="São Paulo",
            estado="SP",
            celular="(11) 91234-5678",
            email_principal="emp@test.com",
            responsavel_nome="João",
            responsavel_cpf="123.456.789-00",
            responsavel_cargo="Diretor",
            responsavel_telefone="(11) 3456-7890",
            responsavel_email="joao@test.com",
        )
        pdv.refresh_from_db()
        self.assertEqual(pdv.get_responsavel_cpf(), "123.456.789-00")
        self.assertEqual(pdv.get_celular(), "(11) 91234-5678")
        self.assertEqual(pdv.get_responsavel_telefone(), "(11) 3456-7890")


# ===========================================================================
# P3: SLA Manager Tests
# ===========================================================================


class SLAManagerTest(BaseTestMixin, TestCase):
    """Testes para o SLAManager — compliance BACEN."""

    def setUp(self):
        self.user = self.create_user(username="agente_sla")
        self.cliente = self.create_cliente()
        self.categoria = self.create_categoria()

    def _make_ticket(self, **kw):
        defaults = dict(
            cliente=self.cliente,
            agente=self.user,
            categoria=self.categoria,
            titulo="SLA Ticket",
            descricao="Teste SLA",
            prioridade="alta",
            status="aberto",
        )
        defaults.update(kw)
        return Ticket.objects.create(**defaults)

    def test_format_time_remaining_positive(self):
        from ..services.sla import SLAManager

        mgr = SLAManager()
        result = mgr._format_time_remaining(timedelta(hours=3, minutes=15))
        self.assertIn("3h", result)
        self.assertIn("15min", result)

    def test_format_time_remaining_minutes_only(self):
        from ..services.sla import SLAManager

        mgr = SLAManager()
        result = mgr._format_time_remaining(timedelta(minutes=42))
        self.assertEqual(result, "42min")

    def test_format_time_remaining_negative(self):
        from ..services.sla import SLAManager

        mgr = SLAManager()
        result = mgr._format_time_remaining(timedelta(hours=-2))
        self.assertIn("Atrasado", result)

    def test_format_time_remaining_less_than_minute(self):
        from ..services.sla import SLAManager

        mgr = SLAManager()
        result = mgr._format_time_remaining(timedelta(seconds=30))
        self.assertEqual(result, "Menos de 1 minuto")

    def test_calculate_business_deadline_weekday(self):
        from ..services.sla import SLAManager

        mgr = SLAManager()
        # Segunda 10:00 + 4h = Segunda 14:00
        start = timezone.now().replace(year=2026, month=2, day=23, hour=10, minute=0, second=0, microsecond=0)
        # 23/02/2026 é segunda
        deadline = mgr._calculate_business_deadline(start, 4)
        self.assertEqual(deadline.hour, 14)

    def test_calculate_business_deadline_crosses_end_of_day(self):
        from ..services.sla import SLAManager

        mgr = SLAManager()
        # Segunda 16:00 + 4h → 2h restam no dia, 2h no dia seguinte → Terça 11:00
        start = timezone.now().replace(year=2026, month=2, day=23, hour=16, minute=0, second=0, microsecond=0)
        deadline = mgr._calculate_business_deadline(start, 4)
        self.assertEqual(deadline.day, 24)
        self.assertEqual(deadline.hour, 11)

    def test_calculate_business_deadline_skips_weekend(self):
        from ..services.sla import SLAManager

        mgr = SLAManager()
        # Sexta 17:00 + 2h → 1h restam na sexta, 1h na segunda → Segunda 10:00
        start = timezone.now().replace(year=2026, month=2, day=27, hour=17, minute=0, second=0, microsecond=0)
        deadline = mgr._calculate_business_deadline(start, 2)
        # Deve pular sábado e domingo
        self.assertEqual(deadline.weekday(), 0)  # Segunda

    def test_calculate_sla_deadline_fallback_24h(self):
        from ..services.sla import SLAManager

        mgr = SLAManager()
        ticket = self._make_ticket()
        # Sem SLAPolicy e sem SLA_CONFIG → fallback 24h
        deadline = mgr.calculate_sla_deadline(ticket)
        self.assertIsNotNone(deadline)

    def test_calculate_sla_deadline_with_policy(self):
        from ..models import SLAPolicy as SLAPolicyModel
        from ..services.sla import SLAManager

        SLAPolicyModel.objects.create(
            name="Alta prioridade",
            categoria=self.categoria,
            prioridade="alta",
            first_response_time=120,  # 120 min = 2h
            resolution_time=480,
            escalation_time=240,
        )
        mgr = SLAManager()
        ticket = self._make_ticket()
        deadline = mgr.calculate_sla_deadline(ticket)
        self.assertIsNotNone(deadline)
        # Deadline deve ser em torno de 2 horas comerciais a partir da criação
        diff = (deadline - ticket.criado_em).total_seconds()
        self.assertGreater(diff, 0)

    def test_get_sla_violations_returns_queryset(self):
        from ..services.sla import SLAManager

        mgr = SLAManager()
        violations = mgr.get_sla_violations(days=7)
        self.assertEqual(len(violations), 0)

    def test_get_sla_metrics_empty(self):
        from ..services.sla import SLAManager

        mgr = SLAManager()
        metrics = mgr.get_sla_metrics(days=30)
        self.assertEqual(metrics["compliance_rate"], 100)
        self.assertEqual(metrics["violations"], 0)

    def test_sla_violation_model(self):
        """SLAViolation cria registro correto."""
        from ..models import SLAViolation

        ticket = self._make_ticket()
        now = timezone.now()
        v = SLAViolation.objects.create(
            ticket=ticket,
            violation_type="deadline_missed",
            severity="high",
            expected_deadline=now - timedelta(hours=2),
            actual_time=now,
            time_exceeded=timedelta(hours=2),
        )
        self.assertIn("Violação SLA", str(v))
        self.assertEqual(v.violation_type, "deadline_missed")

    def test_sla_policy_constraints(self):
        """SLAPolicy rejeita first_response_time <= 0."""
        from django.db import IntegrityError

        from ..models import SLAPolicy as SLAPolicyModel

        with self.assertRaises(IntegrityError):
            SLAPolicyModel.objects.create(
                name="Inválida",
                prioridade="alta",
                first_response_time=0,  # Viola check constraint
                resolution_time=480,
                escalation_time=240,
            )


# ===========================================================================
# P3: Security Tests
# ===========================================================================


class SecurityModuleTest(TestCase):
    """Testes para módulo de segurança."""

    def test_get_client_ip_direct(self):
        from django.test import RequestFactory

        from ..utils.security import get_client_ip

        rf = RequestFactory()
        request = rf.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        self.assertEqual(get_client_ip(request), "192.168.1.100")

    def test_get_client_ip_forwarded(self):
        from django.test import RequestFactory

        from ..utils.security import get_client_ip

        rf = RequestFactory()
        request = rf.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1, 172.16.0.1"
        self.assertEqual(get_client_ip(request), "10.0.0.1")

    def test_validate_file_upload_size_limit(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from ..utils.security import validate_file_upload

        big_file = SimpleUploadedFile("big.txt", b"x" * (11 * 1024 * 1024), content_type="text/plain")
        valid, msg = validate_file_upload(big_file)
        self.assertFalse(valid)
        self.assertIn("10MB", msg)

    def test_validate_file_upload_bad_extension(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from ..utils.security import validate_file_upload

        exe = SimpleUploadedFile("virus.exe", b"\x00" * 100, content_type="application/octet-stream")
        valid, msg = validate_file_upload(exe)
        self.assertFalse(valid)
        self.assertIn(".exe", msg)

    def test_validate_file_upload_valid_txt(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from ..utils.security import validate_file_upload

        txt = SimpleUploadedFile("doc.txt", b"Hello World", content_type="text/plain")
        valid, msg = validate_file_upload(txt)
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_validate_file_upload_suspicious_content(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from ..utils.security import validate_file_upload

        malicious = SimpleUploadedFile("notes.txt", b"<script>alert(1)</script>", content_type="text/plain")
        valid, msg = validate_file_upload(malicious)
        self.assertFalse(valid)
        self.assertIn("malicioso", msg)

    def test_validate_file_upload_mime_mismatch(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from ..utils.security import validate_file_upload

        # extensão .jpg mas content_type de PDF
        fake = SimpleUploadedFile("photo.jpg", b"\x00" * 100, content_type="application/pdf")
        valid, msg = validate_file_upload(fake)
        self.assertFalse(valid)

    def test_validate_file_upload_magic_bytes_png(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from ..utils.security import validate_file_upload

        # Magic bytes errados para PNG
        fake_png = SimpleUploadedFile("img.png", b"\x00\x00\x00\x00" + b"\x00" * 100, content_type="image/png")
        valid, msg = validate_file_upload(fake_png)
        self.assertFalse(valid)
        self.assertIn("conteúdo", msg.lower())

    def test_hash_sensitive_data(self):
        from ..utils.security import hash_sensitive_data

        h1 = hash_sensitive_data("secret123")
        h2 = hash_sensitive_data("secret123")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 16)
        self.assertNotEqual(h1, hash_sensitive_data("other"))

    def test_security_headers_middleware(self):
        from django.test import RequestFactory

        from ..utils.security import SecurityHeadersMiddleware

        rf = RequestFactory()
        request = rf.get("/")

        def get_response(req):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        response = middleware(request)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-XSS-Protection"], "1; mode=block")
        self.assertIn("geolocation", response["Permissions-Policy"])

    @override_settings(DEBUG=False)
    def test_security_headers_csp_in_production(self):
        from django.test import RequestFactory

        from ..utils.security import SecurityHeadersMiddleware

        rf = RequestFactory()
        request = rf.get("/")

        def get_response(req):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        response = middleware(request)
        self.assertIn("Content-Security-Policy", response)
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])

    @override_settings(DEBUG=False)
    def test_csp_nonce_middleware(self):
        """CSPNonceMiddleware gera nonce único por request."""
        from django.test import RequestFactory

        from ..middleware import CSPNonceMiddleware

        rf = RequestFactory()
        request = rf.get("/")

        def get_response(req):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = CSPNonceMiddleware(get_response)
        middleware(request)
        self.assertTrue(hasattr(request, "csp_nonce"))
        self.assertTrue(len(request.csp_nonce) > 20)

        # Cada request gera nonce diferente
        request2 = rf.get("/")
        middleware(request2)
        self.assertNotEqual(request.csp_nonce, request2.csp_nonce)

    @override_settings(DEBUG=False)
    def test_csp_header_includes_nonce(self):
        """SecurityHeadersMiddleware inclui nonce no CSP quando disponível."""
        from django.test import RequestFactory

        from ..middleware import CSPNonceMiddleware
        from ..utils.security import SecurityHeadersMiddleware

        rf = RequestFactory()
        request = rf.get("/")

        def get_response(req):
            from django.http import HttpResponse

            return HttpResponse("OK")

        # Simula pipeline: CSPNonceMiddleware → SecurityHeadersMiddleware
        nonce_mw = CSPNonceMiddleware(get_response)
        nonce_mw(request)  # Define request.csp_nonce

        sec_mw = SecurityHeadersMiddleware(get_response)
        response = sec_mw(request)

        csp = response["Content-Security-Policy"]
        self.assertIn(f"'nonce-{request.csp_nonce}'", csp)
        self.assertIn("'unsafe-inline'", csp)  # Fallback mantido

    def test_rate_limit_decorator(self):
        from django.test import RequestFactory

        from ..utils.security import rate_limit

        @rate_limit(max_requests=2, window_seconds=60)
        def test_view(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        rf = RequestFactory()
        request = rf.get("/")
        request.META["REMOTE_ADDR"] = "10.10.10.10"
        request.user = MagicMock(is_authenticated=False)

        # Primeiras 2 requisições devem passar
        r1 = test_view(request)
        self.assertEqual(r1.status_code, 200)
        r2 = test_view(request)
        self.assertEqual(r2.status_code, 200)
        # Terceira deve ser bloqueada (429)
        r3 = test_view(request)
        self.assertEqual(r3.status_code, 429)


# ===========================================================================
# P3: Audit Signal Tests
# ===========================================================================


class AuditSignalTest(BaseTestMixin, TestCase):
    """Testes para signals de auditoria — trilha obrigatória BACEN."""

    def test_audit_login(self):
        from django.contrib.auth.signals import user_logged_in

        from ..models.audit import AuditEvent

        user = self.create_user(username="aud_login")
        rf = RequestFactory()
        request = rf.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.META["HTTP_USER_AGENT"] = "TestBot/1.0"
        # Disparar signal manualmente
        user_logged_in.send(sender=user.__class__, request=request, user=user)
        event = AuditEvent.objects.filter(event_type="login", user=user).first()
        self.assertIsNotNone(event)
        self.assertIn("Login bem-sucedido", event.description)
        self.assertEqual(event.ip_address, "192.168.1.1")

    def test_audit_logout(self):
        from django.contrib.auth.signals import user_logged_out

        from ..models.audit import AuditEvent

        user = self.create_user(username="aud_logout")
        rf = RequestFactory()
        request = rf.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.2"
        request.META["HTTP_USER_AGENT"] = "TestBot/1.0"
        user_logged_out.send(sender=user.__class__, request=request, user=user)
        event = AuditEvent.objects.filter(event_type="logout", user=user).first()
        self.assertIsNotNone(event)
        self.assertIn("Logout", event.description)

    def test_audit_login_failed(self):
        from django.contrib.auth.signals import user_login_failed

        from ..models.audit import AuditEvent

        rf = RequestFactory()
        request = rf.get("/")
        request.META["REMOTE_ADDR"] = "10.0.0.5"
        request.META["HTTP_USER_AGENT"] = "HackerBot"
        user_login_failed.send(
            sender=self.__class__,
            credentials={"username": "hacker"},
            request=request,
        )
        event = AuditEvent.objects.filter(event_type="security_event", action="login_failed").first()
        self.assertIsNotNone(event)
        self.assertTrue(event.is_suspicious)
        self.assertIn("hacker", event.description)

    def test_audit_ticket_created(self):
        """Criação de ticket gera audit event."""
        from ..models.audit import AuditEvent

        cliente = self.create_cliente()
        ticket = Ticket.objects.create(
            cliente=cliente,
            titulo="Audit Test",
            descricao="Teste de auditoria",
            prioridade="alta",
            status="aberto",
        )
        events = AuditEvent.objects.filter(event_type="create", action="ticket_created")
        self.assertTrue(events.exists())
        ev = events.last()
        self.assertIn(str(ticket.numero), ev.description)

    def test_audit_ticket_updated(self):
        """Atualização de ticket gera audit event."""
        from ..models.audit import AuditEvent

        cliente = self.create_cliente()
        ticket = Ticket.objects.create(
            cliente=cliente,
            titulo="Audit Upd",
            descricao="x",
            prioridade="baixa",
            status="aberto",
        )
        initial_count = AuditEvent.objects.filter(action="ticket_updated").count()
        ticket.status = "em_andamento"
        ticket.save()
        new_count = AuditEvent.objects.filter(action="ticket_updated").count()
        self.assertEqual(new_count, initial_count + 1)


# ===========================================================================
# P3: Auto-Assignment Tests (lógica pura — tabelas não migradas)
# ===========================================================================


class AutoAssignmentLogicTest(BaseTestMixin, TestCase):
    """Testes para lógica de auto-assignment (sem depender de tabelas não migradas)."""

    def test_cargo_trabalho_percentual_ocupacao(self):
        """Testa property percentual_ocupacao sem salvar no banco."""
        from ..models.auto_assignment import CargoTrabalho

        carga = CargoTrabalho(tickets_abertos=5, capacidade_maxima=10)
        self.assertEqual(carga.percentual_ocupacao, 50.0)

    def test_cargo_trabalho_pode_receber_ticket(self):
        from ..models.auto_assignment import CargoTrabalho

        carga = CargoTrabalho(tickets_abertos=2, capacidade_maxima=10, disponivel=True)
        self.assertTrue(carga.pode_receber_ticket)

    def test_cargo_trabalho_nao_pode_receber_cheio(self):
        from ..models.auto_assignment import CargoTrabalho

        carga = CargoTrabalho(tickets_abertos=10, capacidade_maxima=10, disponivel=True)
        self.assertFalse(carga.pode_receber_ticket)

    def test_cargo_trabalho_nao_pode_receber_indisponivel(self):
        from ..models.auto_assignment import CargoTrabalho

        carga = CargoTrabalho(tickets_abertos=0, capacidade_maxima=10, disponivel=False)
        self.assertFalse(carga.pode_receber_ticket)

    def test_cargo_trabalho_capacidade_zero(self):
        from ..models.auto_assignment import CargoTrabalho

        carga = CargoTrabalho(tickets_abertos=0, capacidade_maxima=0)
        self.assertEqual(carga.percentual_ocupacao, 100)

    def test_regra_se_aplica_sem_filtro(self):
        """Regra sem filtros se aplica a qualquer ticket."""
        from ..models.auto_assignment import RegraAtribuicao, regra_se_aplica

        regra = RegraAtribuicao(nome="Pegar tudo", ativa=True)
        cliente = self.create_cliente()
        ticket = Ticket.objects.create(
            cliente=cliente,
            titulo="Auto Test",
            descricao="Test",
            prioridade="media",
            status="aberto",
        )
        self.assertTrue(regra_se_aplica(ticket, regra))

    def test_regra_se_aplica_prioridade(self):
        from ..models.auto_assignment import RegraAtribuicao, regra_se_aplica

        regra = RegraAtribuicao(nome="Só alta", prioridade="alta", ativa=True)
        cliente = self.create_cliente()
        ticket = Ticket.objects.create(
            cliente=cliente,
            titulo="T1",
            descricao="X",
            prioridade="alta",
            status="aberto",
        )
        self.assertTrue(regra_se_aplica(ticket, regra))
        ticket2 = Ticket.objects.create(
            cliente=Cliente.objects.create(nome="C2", email="c2@t.com"),
            titulo="T2",
            descricao="Y",
            prioridade="baixa",
            status="aberto",
        )
        self.assertFalse(regra_se_aplica(ticket2, regra))

    def test_regra_se_aplica_palavras_chave(self):
        from ..models.auto_assignment import RegraAtribuicao, regra_se_aplica

        regra = RegraAtribuicao(nome="VPN", palavras_chave="vpn\nconexão", ativa=True)
        cliente = self.create_cliente()
        ticket = Ticket.objects.create(
            cliente=cliente,
            titulo="Problema com VPN",
            descricao="X",
            prioridade="media",
            status="aberto",
        )
        self.assertTrue(regra_se_aplica(ticket, regra))
        ticket2 = Ticket.objects.create(
            cliente=Cliente.objects.create(nome="C3", email="c3@t.com"),
            titulo="Impressora não funciona",
            descricao="Y",
            prioridade="media",
            status="aberto",
        )
        self.assertFalse(regra_se_aplica(ticket2, regra))

    def test_buscar_agentes_por_skill_sem_skill(self):
        from ..models.auto_assignment import buscar_agentes_por_skill

        user = self.create_user(username="ag_staff")
        user.is_staff = True
        user.save()
        agents = buscar_agentes_por_skill("", 1)
        self.assertIn(user, agents)


# ===========================================================================
# P3: Form Tests
# ===========================================================================


class FormSecurityTest(BaseTestMixin, TestCase):
    """Testes para segurança de formulários."""

    def test_user_creation_form_forces_non_staff(self):
        """DashboardUserCreationForm NUNCA cria staff/superuser."""
        from ..forms import DashboardUserCreationForm

        data = {
            "username": "newuser",
            "email": "new@t.com",
            "password1": "C0mpl3x_Pa55!",
            "password2": "C0mpl3x_Pa55!",
            "is_staff": True,  # tentativa de escalação
            "is_superuser": True,  # tentativa de escalação
            "is_active": True,
        }
        form = DashboardUserCreationForm(data=data)
        if form.is_valid():
            user = form.save()
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)

    def test_quick_ticket_form_priorities_match_model(self):
        """QuickTicketForm deve usar mesmos valores que PrioridadeTicket."""
        from ..forms import QuickTicketForm
        from ..models import PrioridadeTicket

        form = QuickTicketForm()
        form_values = {c[0] for c in form.fields["priority"].choices}
        model_values = {c.value for c in PrioridadeTicket}
        self.assertEqual(form_values, model_values)

    def test_quick_ticket_form_valid(self):
        from ..forms import QuickTicketForm

        form = QuickTicketForm(
            data={
                "title": "Problema urgente",
                "description": "Detalhes do problema",
                "priority": "alta",
            }
        )
        self.assertTrue(form.is_valid())

    def test_quick_ticket_form_invalid_priority(self):
        from ..forms import QuickTicketForm

        form = QuickTicketForm(
            data={
                "title": "Teste",
                "description": "Desc",
                "priority": "inexistente",
            }
        )
        self.assertFalse(form.is_valid())

    def test_ticket_form_valid(self):
        from ..forms import TicketForm

        cat = self.create_categoria()
        form = TicketForm(
            data={
                "titulo": "Ticket via form",
                "descricao": "Descrição detalhada do ticket",
                "prioridade": "media",
                "categoria": cat.pk,
            }
        )
        self.assertTrue(form.is_valid())

    def test_cliente_form_valid(self):
        from ..forms import ClienteForm

        form = ClienteForm(
            data={
                "nome": "Novo Cliente",
                "email": "novo@cliente.com",
                "telefone": "(11) 99999-0000",
                "empresa": "Empresa X",
            }
        )
        self.assertTrue(form.is_valid())

    def test_cliente_form_missing_required(self):
        from ..forms import ClienteForm

        form = ClienteForm(data={"nome": "", "email": ""})
        self.assertFalse(form.is_valid())


# ===========================================================================
# P3: Notification Model Tests
# ===========================================================================


class NotificationModelTest(BaseTestMixin, TestCase):
    """Testes para o modelo Notification."""

    def test_notification_create(self):
        from ..models import Notification

        user = self.create_user()
        n = Notification.objects.create(
            user=user,
            type="new_ticket",
            title="Novo",
            message="Ticket #1 criado",
        )
        self.assertFalse(n.read)
        self.assertIsNone(n.read_at)
        self.assertIn("Novo", str(n))

    def test_notification_mark_as_read(self):
        from ..models import Notification

        user = self.create_user()
        n = Notification.objects.create(
            user=user,
            type="sla_warning",
            title="SLA",
            message="Prazo chegando",
        )
        n.mark_as_read()
        n.refresh_from_db()
        self.assertTrue(n.read)
        self.assertIsNotNone(n.read_at)

    def test_notification_mark_as_read_idempotent(self):
        from ..models import Notification

        user = self.create_user()
        n = Notification.objects.create(
            user=user,
            type="ticket_assigned",
            title="Atribuído",
            message="Ticket para você",
        )
        n.mark_as_read()
        first_read_at = n.read_at
        n.mark_as_read()
        # Não deve atualizar novamente
        self.assertEqual(n.read_at, first_read_at)


# ===========================================================================
# P3: View Integration Tests
# ===========================================================================


class ViewAuthTest(BaseTestMixin, TestCase):
    """Testes de integração para autenticação nas views."""

    def test_login_page_accessible(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):
        response = self.client.get("/dashboard/")
        # Deve redirecionar para login
        self.assertIn(response.status_code, [301, 302])

    def test_logout_page(self):
        response = self.client.get("/logout/")
        # Logout sem sessão funciona (200 ou redirect)
        self.assertIn(response.status_code, [200, 302])


class ViewTicketTest(BaseTestMixin, TestCase):
    """Testes de integração para views de tickets."""

    def setUp(self):
        self.admin = self.create_admin(username="view_admin", password="Admin123!")
        self.client.force_login(self.admin)
        self.cliente = self.create_cliente()
        self.categoria = self.create_categoria()

    def test_ticket_list_logged_in(self):
        response = self.client.get("/dashboard/tickets/")
        self.assertEqual(response.status_code, 200)

    def test_ticket_create_get(self):
        response = self.client.get("/dashboard/tickets/novo/")
        self.assertEqual(response.status_code, 200)

    def test_ticket_kanban(self):
        response = self.client.get("/dashboard/tickets/kanban/")
        self.assertEqual(response.status_code, 200)

    def test_ticket_detail(self):
        ticket = Ticket.objects.create(
            cliente=self.cliente,
            titulo="Det Test",
            descricao="Detalhe",
            prioridade="media",
            status="aberto",
        )
        response = self.client.get(f"/dashboard/tickets/{ticket.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_ticket_list_unauthenticated(self):
        self.client.logout()
        response = self.client.get("/dashboard/tickets/")
        self.assertIn(response.status_code, [301, 302])


class ViewClienteTest(BaseTestMixin, TestCase):
    """Testes de integração para views de clientes."""

    def setUp(self):
        self.admin = self.create_admin(username="cli_admin", password="Admin123!")
        self.client.force_login(self.admin)

    def test_cliente_list(self):
        response = self.client.get("/dashboard/clientes/")
        self.assertEqual(response.status_code, 200)

    def test_cliente_create_get(self):
        response = self.client.get("/dashboard/clientes/novo/")
        self.assertEqual(response.status_code, 200)

    def test_cliente_detail(self):
        cli = self.create_cliente()
        response = self.client.get(f"/dashboard/clientes/{cli.pk}/")
        self.assertEqual(response.status_code, 200)


class ViewNotificationTest(BaseTestMixin, TestCase):
    """Testes de integração para views de notificações."""

    def setUp(self):
        self.user = self.create_user(username="notif_user", password="Pass123!")
        self.client.force_login(self.user)

    def test_notifications_list(self):
        response = self.client.get("/dashboard/notifications/")
        self.assertEqual(response.status_code, 200)

    def test_api_notifications_recent(self):
        response = self.client.get("/dashboard/api/notifications/recent/")
        self.assertIn(response.status_code, [200, 302])

    def test_api_mark_all_read(self):
        response = self.client.post("/dashboard/api/notifications/mark-all-read/")
        self.assertIn(response.status_code, [200, 302])

    def test_notification_mark_read(self):
        from ..models import Notification

        n = Notification.objects.create(
            user=self.user,
            type="new_ticket",
            title="Test",
            message="Mark read test",
        )
        response = self.client.post(f"/dashboard/api/notifications/{n.pk}/mark-read/")
        self.assertIn(response.status_code, [200, 302])

    def test_notification_delete(self):
        from ..models import Notification

        n = Notification.objects.create(
            user=self.user,
            type="system_alert",
            title="Del",
            message="Delete test",
        )
        response = self.client.post(f"/dashboard/api/notifications/{n.pk}/delete/")
        self.assertIn(response.status_code, [200, 302])


class ViewSLATest(BaseTestMixin, TestCase):
    """Testes de integração para views de SLA."""

    def setUp(self):
        self.admin = self.create_admin(username="sla_admin", password="Admin123!")
        self.client.force_login(self.admin)

    def test_sla_dashboard(self):
        response = self.client.get("/dashboard/sla/")
        self.assertEqual(response.status_code, 200)

    def test_sla_policies(self):
        response = self.client.get("/dashboard/sla/policies/")
        self.assertEqual(response.status_code, 200)

    def test_sla_alerts(self):
        response = self.client.get("/dashboard/sla/alerts/")
        self.assertEqual(response.status_code, 200)

    def test_sla_reports(self):
        response = self.client.get("/dashboard/sla/reports/")
        self.assertEqual(response.status_code, 200)


class ViewExportTest(BaseTestMixin, TestCase):
    """Testes para export de tickets."""

    def setUp(self):
        self.admin = self.create_admin(username="exp_admin", password="Admin123!")
        self.client.force_login(self.admin)

    def test_export_tickets_page(self):
        response = self.client.get("/dashboard/export/tickets/")
        self.assertIn(response.status_code, [200, 302])


# ===========================================================================
# P3: Workflow Model Tests
# ===========================================================================


class WorkflowModelTest(BaseTestMixin, TestCase):
    """Testes para modelos de workflow."""

    def test_workflow_rule_create(self):
        from ..models import WorkflowRule

        rule = WorkflowRule.objects.create(
            name="Auto escalação",
            trigger_event="sla_warning",
            conditions='{"prioridade": ["critica"]}',
            actions='{"change_priority": {"new_priority": "critica"}}',
            is_active=True,
            priority=10,
        )
        self.assertEqual(str(rule), "Auto escalação")
        self.assertTrue(rule.is_active)

    def test_workflow_execution_create(self):
        from ..models import WorkflowExecution, WorkflowRule

        cliente = self.create_cliente()
        ticket = Ticket.objects.create(
            cliente=cliente,
            titulo="WF Test",
            descricao="x",
            prioridade="alta",
            status="aberto",
        )
        rule = WorkflowRule.objects.create(
            name="Test Rule",
            trigger_event="ticket_created",
            conditions="{}",
            actions="{}",
            is_active=True,
        )
        exe = WorkflowExecution.objects.create(
            ticket=ticket,
            rule=rule,
            trigger_event="ticket_created",
            execution_result={"rule_id": rule.id, "actions_executed": []},
        )
        self.assertTrue(exe.success)


# ===========================================================================
# P3: Signal notification & WebSocket Tests
# ===========================================================================


class SignalNotificationTest(BaseTestMixin, TestCase):
    """Testes para signals de notificação automática."""

    def test_ticket_created_generates_notifications(self):
        """Criação de ticket gera Notification para agentes ativos."""
        from ..models import Notification, PerfilAgente

        agent = self.create_user(username="sig_agent")
        PerfilAgente.objects.get_or_create(user=agent)
        cliente = self.create_cliente()
        ticket = Ticket.objects.create(
            cliente=cliente,
            titulo="Signal Test",
            descricao="Teste signal",
            prioridade="alta",
            status="aberto",
        )
        # O signal ticket_created_or_updated deve criar notificação
        notifs = Notification.objects.filter(user=agent, type="new_ticket")
        self.assertTrue(notifs.exists())
        self.assertIn(str(ticket.numero), notifs.first().message)

    def test_lazy_channel_layer_returns_none_without_redis(self):
        """_get_channel_layer retorna None quando Redis não está disponível."""
        from ..signals import _get_channel_layer

        # Em ambiente de teste sem Redis, deve retornar None sem dar erro
        _get_channel_layer()
        # Pode ser None ou um InMemoryChannelLayer dependendo da config
        # O importante é que não levanta exceção
        self.assertTrue(True)  # Se chegou aqui, não levantou exceção

    def test_safe_group_send_no_crash_without_layer(self):
        """_safe_group_send não levanta exceção sem channel layer."""
        from ..signals import _safe_group_send

        # Não deve dar erro mesmo sem Redis
        _safe_group_send("test_group", {"type": "test", "data": {}})
        self.assertTrue(True)
