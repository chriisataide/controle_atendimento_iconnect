"""
Testes de Views — Dashboard, tickets, clientes, login/logout.
"""
from django.test import TestCase, Client
from django.urls import reverse

from dashboard.models import Ticket, StatusTicket
from .factories import UserFactory, AdminFactory, ClienteFactory, TicketFactory


class LoginViewTest(TestCase):
    def test_login_page_loads(self):
        resp = self.client.get(reverse('login'))
        self.assertEqual(resp.status_code, 200)

    def test_login_success(self):
        user = UserFactory()
        resp = self.client.post(reverse('login'), {
            'username': user.username,
            'password': 'testpass123',
        })
        self.assertIn(resp.status_code, [200, 302])

    def test_login_fail(self):
        resp = self.client.post(reverse('login'), {
            'username': 'nobody',
            'password': 'wrong',
        })
        self.assertEqual(resp.status_code, 200)  # Re-render form

    def test_logout(self):
        user = UserFactory()
        self.client.login(username=user.username, password='testpass123')
        resp = self.client.get(reverse('logout'))
        self.assertIn(resp.status_code, [200, 302])


class DashboardViewTest(TestCase):
    def setUp(self):
        self.user = AdminFactory()
        self.client.login(username=self.user.username, password='testpass123')

    def test_dashboard_loads(self):
        resp = self.client.get(reverse('dashboard:index'))
        self.assertIn(resp.status_code, [200, 302])

    def test_dashboard_unauthenticated_redirects(self):
        self.client.logout()
        resp = self.client.get(reverse('dashboard:index'))
        self.assertEqual(resp.status_code, 302)


class TicketViewTest(TestCase):
    def setUp(self):
        self.user = AdminFactory()
        self.client.login(username=self.user.username, password='testpass123')

    def test_ticket_list(self):
        TicketFactory.create_batch(3)
        resp = self.client.get(reverse('dashboard:ticket_list'))
        self.assertIn(resp.status_code, [200, 302])

    def test_ticket_create_page(self):
        resp = self.client.get(reverse('dashboard:ticket_create'))
        self.assertIn(resp.status_code, [200, 302])

    def test_ticket_detail(self):
        t = TicketFactory()
        resp = self.client.get(reverse('dashboard:ticket_detail', kwargs={'pk': t.pk}))
        self.assertIn(resp.status_code, [200, 302])

    def test_kanban_view(self):
        resp = self.client.get(reverse('dashboard:ticket_kanban'))
        self.assertIn(resp.status_code, [200, 302])


class ClienteViewTest(TestCase):
    def setUp(self):
        self.user = AdminFactory()
        self.client.login(username=self.user.username, password='testpass123')

    def test_cliente_list(self):
        ClienteFactory.create_batch(3)
        resp = self.client.get(reverse('dashboard:cliente_list'))
        self.assertIn(resp.status_code, [200, 302])

    def test_cliente_create_page(self):
        resp = self.client.get(reverse('dashboard:cliente_create'))
        self.assertIn(resp.status_code, [200, 302])


class SLAViewTest(TestCase):
    def setUp(self):
        self.user = AdminFactory()
        self.client.login(username=self.user.username, password='testpass123')

    def test_sla_dashboard(self):
        resp = self.client.get(reverse('dashboard:sla_dashboard'))
        self.assertIn(resp.status_code, [200, 302])

    def test_sla_policies(self):
        resp = self.client.get(reverse('dashboard:sla_policies'))
        self.assertIn(resp.status_code, [200, 302])


class ReportsViewTest(TestCase):
    def setUp(self):
        self.user = AdminFactory()
        self.client.login(username=self.user.username, password='testpass123')

    def test_reports_dashboard(self):
        resp = self.client.get(reverse('dashboard:reports'))
        self.assertIn(resp.status_code, [200, 302])


class ChatViewTest(TestCase):
    def setUp(self):
        self.user = AdminFactory()
        self.client.login(username=self.user.username, password='testpass123')

    def test_chat_dashboard(self):
        resp = self.client.get(reverse('dashboard:chat_dashboard'))
        self.assertIn(resp.status_code, [200, 302])


class AnalyticsViewTest(TestCase):
    def setUp(self):
        self.user = AdminFactory()
        self.client.login(username=self.user.username, password='testpass123')

    def test_analytics_dashboard(self):
        resp = self.client.get(reverse('dashboard:analytics_dashboard'))
        self.assertIn(resp.status_code, [200, 302])


class SearchViewTest(TestCase):
    def setUp(self):
        self.user = AdminFactory()
        self.client.login(username=self.user.username, password='testpass123')

    def test_search_page(self):
        resp = self.client.get(reverse('dashboard:search'))
        self.assertIn(resp.status_code, [200, 302])


class AutomationViewTest(TestCase):
    def setUp(self):
        self.user = AdminFactory()
        self.client.login(username=self.user.username, password='testpass123')

    def test_automation_dashboard(self):
        resp = self.client.get(reverse('dashboard:automation'))
        self.assertIn(resp.status_code, [200, 302])

    def test_automation_workflows(self):
        resp = self.client.get(reverse('dashboard:automation_workflows'))
        self.assertIn(resp.status_code, [200, 302])
