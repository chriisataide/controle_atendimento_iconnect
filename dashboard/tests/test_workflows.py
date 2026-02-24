"""
Testes para o Visual Workflow Builder.
"""
import json
from django.test import TestCase
from django.contrib.auth.models import User

from dashboard.models import WorkflowRule


class WorkflowBuilderCatalogTest(TestCase):
    """Testes do catálogo de componentes"""

    def setUp(self):
        self.user = User.objects.create_user(username='wf_user', password='test123')
        self.client.login(username='wf_user', password='test123')

    def test_catalog_endpoint(self):
        resp = self.client.get('/dashboard/api/workflows/catalog/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('triggers', data)
        self.assertIn('conditions', data)
        self.assertIn('actions', data)
        self.assertIn('templates', data)
        self.assertTrue(len(data['triggers']) > 0)

    def test_catalog_has_required_triggers(self):
        resp = self.client.get('/dashboard/api/workflows/catalog/')
        data = resp.json()
        trigger_ids = [t['id'] for t in data['triggers']]
        self.assertIn('ticket_created', trigger_ids)
        self.assertIn('sla_breach', trigger_ids)


class WorkflowBuilderCRUDTest(TestCase):
    """Testes de CRUD de workflows via builder"""

    def setUp(self):
        self.user = User.objects.create_user(username='wf_crud', password='test123')
        self.client.login(username='wf_crud', password='test123')

    def test_create_workflow(self):
        resp = self.client.post(
            '/dashboard/api/workflows/create/',
            json.dumps({
                'name': 'Meu Workflow',
                'trigger_event': 'ticket_created',
                'conditions': {'prioridade': ['alta']},
                'actions': {'change_status': {'new_status': 'em_andamento'}},
                'priority': 5,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(WorkflowRule.objects.count(), 1)

    def test_create_requires_name(self):
        resp = self.client.post(
            '/dashboard/api/workflows/create/',
            json.dumps({'trigger_event': 'ticket_created', 'actions': {}}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_list_workflows(self):
        WorkflowRule.objects.create(
            name='Rule 1', trigger_event='ticket_created',
            conditions={}, actions={'escalate': {'level': 1}},
        )
        resp = self.client.get('/dashboard/api/workflows/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['rules']), 1)

    def test_update_workflow(self):
        rule = WorkflowRule.objects.create(
            name='To Update', trigger_event='ticket_created',
            conditions={}, actions={},
        )
        resp = self.client.put(
            f'/dashboard/api/workflows/{rule.id}/update/',
            json.dumps({'name': 'Updated Name', 'priority': 9}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        rule.refresh_from_db()
        self.assertEqual(rule.name, 'Updated Name')
        self.assertEqual(rule.priority, 9)

    def test_delete_workflow(self):
        rule = WorkflowRule.objects.create(
            name='To Delete', trigger_event='ticket_created',
            conditions={}, actions={},
        )
        resp = self.client.delete(f'/dashboard/api/workflows/{rule.id}/delete/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(WorkflowRule.objects.count(), 0)

    def test_toggle_workflow(self):
        rule = WorkflowRule.objects.create(
            name='Toggle', trigger_event='ticket_created',
            conditions={}, actions={}, is_active=True,
        )
        resp = self.client.post(f'/dashboard/api/workflows/{rule.id}/toggle/')
        self.assertEqual(resp.status_code, 200)
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)

    def test_duplicate_workflow(self):
        rule = WorkflowRule.objects.create(
            name='Original', trigger_event='ticket_created',
            conditions={'status': ['aberto']}, actions={'escalate': {'level': 1}},
        )
        resp = self.client.post(f'/dashboard/api/workflows/{rule.id}/duplicate/')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(WorkflowRule.objects.count(), 2)
        copy = WorkflowRule.objects.exclude(id=rule.id).first()
        self.assertIn('cópia', copy.name)
        self.assertFalse(copy.is_active)


class WorkflowBuilderTemplateTest(TestCase):
    """Testes de templates pré-definidos"""

    def setUp(self):
        self.user = User.objects.create_user(username='wf_tmpl', password='test123')
        self.client.login(username='wf_tmpl', password='test123')

    def test_from_template(self):
        resp = self.client.post(
            '/dashboard/api/workflows/from-template/',
            json.dumps({'template_name': 'auto_assign_high_priority'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(WorkflowRule.objects.count(), 1)

    def test_invalid_template(self):
        resp = self.client.post(
            '/dashboard/api/workflows/from-template/',
            json.dumps({'template_name': 'nonexistent'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)


class WorkflowBuilderValidationTest(TestCase):
    """Testes de validação"""

    def setUp(self):
        self.user = User.objects.create_user(username='wf_val', password='test123')
        self.client.login(username='wf_val', password='test123')

    def test_valid_workflow(self):
        resp = self.client.post(
            '/dashboard/api/workflows/validate/',
            json.dumps({
                'trigger_event': 'ticket_created',
                'conditions': {'prioridade': ['alta']},
                'actions': {'change_status': {'new_status': 'em_andamento'}},
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['valid'])

    def test_invalid_trigger(self):
        resp = self.client.post(
            '/dashboard/api/workflows/validate/',
            json.dumps({
                'trigger_event': 'invalid_event',
                'conditions': {},
                'actions': {'escalate': {}},
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_no_actions(self):
        resp = self.client.post(
            '/dashboard/api/workflows/validate/',
            json.dumps({
                'trigger_event': 'ticket_created',
                'conditions': {},
                'actions': {},
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_condition_key(self):
        resp = self.client.post(
            '/dashboard/api/workflows/validate/',
            json.dumps({
                'trigger_event': 'ticket_created',
                'conditions': {'nonexistent_condition': True},
                'actions': {'escalate': {}},
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('nonexistent_condition', str(resp.json()['errors']))


class WorkflowBuilderMetricsTest(TestCase):
    """Testes de métricas"""

    def setUp(self):
        self.user = User.objects.create_user(username='wf_met', password='test123')
        self.client.login(username='wf_met', password='test123')

    def test_metrics_endpoint(self):
        resp = self.client.get('/dashboard/api/workflows/metrics/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('total_executions', data)
        self.assertIn('success_rate', data)

    def test_metrics_custom_days(self):
        resp = self.client.get('/dashboard/api/workflows/metrics/?days=7')
        self.assertEqual(resp.status_code, 200)


class WorkflowBuilderViewTest(TestCase):
    """Testes da view do builder"""

    def setUp(self):
        self.user = User.objects.create_user(username='wf_view', password='test123')
        self.client.login(username='wf_view', password='test123')

    def test_builder_page_loads(self):
        resp = self.client.get('/dashboard/workflows/builder/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Visual Workflow Builder')
        self.assertContains(resp, 'builderCanvas')

    def test_requires_auth(self):
        self.client.logout()
        resp = self.client.get('/dashboard/workflows/builder/')
        self.assertEqual(resp.status_code, 302)
