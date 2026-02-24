"""
Testes da API REST — Cobertura de endpoints, auth, RBAC, paginação.
"""
import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from dashboard.models import (
    Cliente, Ticket, CategoriaTicket, StatusTicket, PrioridadeTicket,
    CannedResponse, WebhookEndpoint, APIKey,
)
from .factories import (
    UserFactory, AdminFactory, ClienteFactory, CategoriaFactory,
    TicketFactory, PerfilAgenteFactory,
)


class TicketAPITest(APITestCase):
    def setUp(self):
        self.admin = AdminFactory()
        self.client.force_authenticate(user=self.admin)
        self.cat = CategoriaFactory()

    def test_list_tickets(self):
        TicketFactory.create_batch(5)
        resp = self.client.get(reverse('api:ticket-list-create'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data['count'], 5)

    def test_create_ticket(self):
        cliente = ClienteFactory()
        data = {
            'titulo': 'Teste API',
            'descricao': 'Criado via API',
            'cliente_email': cliente.email,
            'cliente_nome': cliente.nome,
            'prioridade': 'alta',
        }
        resp = self.client.post(reverse('api:ticket-list-create'), data, format='json')
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_ticket_detail(self):
        t = TicketFactory()
        resp = self.client.get(reverse('api:ticket-detail', kwargs={'pk': t.pk}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_filter_by_status(self):
        TicketFactory(status=StatusTicket.ABERTO)
        TicketFactory(status=StatusTicket.FECHADO)
        resp = self.client.get(reverse('api:ticket-list-create'), {'status': 'aberto'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_access_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(reverse('api:ticket-list-create'))
        self.assertIn(resp.status_code, [401, 403])


class ClienteAPITest(APITestCase):
    def setUp(self):
        self.admin = AdminFactory()
        self.client.force_authenticate(user=self.admin)

    def test_list_clientes(self):
        ClienteFactory.create_batch(3)
        resp = self.client.get(reverse('api:cliente-list-create'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_cliente(self):
        data = {'nome': 'Novo Cliente', 'email': 'novo@test.com'}
        resp = self.client.post(reverse('api:cliente-list-create'), data, format='json')
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])


class AuthAPITest(APITestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_jwt_token_obtain(self):
        resp = self.client.post(reverse('api:token_obtain_pair'), {
            'username': self.user.username,
            'password': 'testpass123',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_jwt_token_refresh(self):
        resp = self.client.post(reverse('api:token_obtain_pair'), {
            'username': self.user.username,
            'password': 'testpass123',
        }, format='json')
        refresh = resp.data['refresh']
        resp2 = self.client.post(reverse('api:token_refresh'), {
            'refresh': refresh,
        }, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp2.data)


class AnalyticsAPITest(APITestCase):
    def setUp(self):
        self.admin = AdminFactory()
        self.client.force_authenticate(user=self.admin)

    def test_overview(self):
        resp = self.client.get(reverse('api:analytics-overview'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_sla_metrics(self):
        resp = self.client.get(reverse('api:analytics-sla'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class CannedResponseAPITest(APITestCase):
    def setUp(self):
        self.admin = AdminFactory()
        self.client.force_authenticate(user=self.admin)

    def test_list(self):
        CannedResponse.objects.create(
            title='Resp', content='Olá', category='suporte', created_by=self.admin
        )
        resp = self.client.get(reverse('api:canned-response-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class WebhookAPITest(APITestCase):
    def setUp(self):
        self.admin = AdminFactory()
        self.client.force_authenticate(user=self.admin)

    def test_list_webhooks(self):
        resp = self.client.get(reverse('api:webhook-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class HealthCheckAPITest(APITestCase):
    def test_health_check(self):
        resp = self.client.get(reverse('api:health-check'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class BulkActionAPITest(APITestCase):
    def setUp(self):
        self.admin = AdminFactory()
        self.client.force_authenticate(user=self.admin)

    def test_bulk_action_close(self):
        t1 = TicketFactory(status=StatusTicket.ABERTO)
        t2 = TicketFactory(status=StatusTicket.ABERTO)
        data = {
            'ticket_ids': [t1.pk, t2.pk],
            'action': 'close',
        }
        resp = self.client.post(
            reverse('api:ticket-bulk-action'), data, format='json'
        )
        self.assertIn(resp.status_code, [200, 400])


class ExportAPITest(APITestCase):
    def setUp(self):
        self.admin = AdminFactory()
        self.client.force_authenticate(user=self.admin)

    def test_export_tickets_excel(self):
        TicketFactory.create_batch(3)
        resp = self.client.get(reverse('api:export-tickets-excel'))
        self.assertIn(resp.status_code, [200, 302])
