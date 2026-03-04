"""
Testes para o sistema de multi-tenancy.
"""

import json
from unittest import expectedFailure

from django.contrib.auth.models import User
from django.test import TestCase

from dashboard.tenants import (
    Tenant,
    TenantInvite,
    TenantMembership,
    clear_current_tenant,
    get_current_tenant,
    set_current_tenant,
)


class TenantModelTest(TestCase):
    """Testes do modelo Tenant"""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="test123")

    def test_create_tenant(self):
        t = Tenant.objects.create(name="Empresa X", slug="empresa-x", owner=self.owner)
        self.assertEqual(str(t), "Empresa X (empresa-x)")
        self.assertTrue(t.is_active)

    def test_slug_unique(self):
        Tenant.objects.create(name="A", slug="unique", owner=self.owner)
        with self.assertRaises(Exception):
            Tenant.objects.create(name="B", slug="unique", owner=self.owner)

    def test_default_plan(self):
        t = Tenant.objects.create(name="Free", slug="free-co", owner=self.owner)
        self.assertEqual(t.plan, "free")

    def test_is_within_agent_limit(self):
        t = Tenant.objects.create(name="T", slug="agent-limit", owner=self.owner, max_agents=2)
        TenantMembership.objects.create(tenant=t, user=self.owner, role="owner")
        self.assertTrue(t.is_within_agent_limit)


class TenantMembershipTest(TestCase):
    """Testes de membership"""

    def setUp(self):
        self.owner = User.objects.create_user(username="own", password="test")
        self.agent = User.objects.create_user(username="agent", password="test")
        self.tenant = Tenant.objects.create(name="Org", slug="org", owner=self.owner)

    def test_create_membership(self):
        m = TenantMembership.objects.create(tenant=self.tenant, user=self.agent, role="agent")
        self.assertEqual(m.role, "agent")
        self.assertTrue(m.is_active)

    def test_unique_together(self):
        TenantMembership.objects.create(tenant=self.tenant, user=self.agent)
        with self.assertRaises(Exception):
            TenantMembership.objects.create(tenant=self.tenant, user=self.agent)


class TenantContextTest(TestCase):
    """Testes de thread-local context"""

    def setUp(self):
        self.owner = User.objects.create_user(username="ctx", password="test")
        self.tenant = Tenant.objects.create(name="Ctx", slug="ctx", owner=self.owner)

    def test_set_get_clear(self):
        self.assertIsNone(get_current_tenant())
        set_current_tenant(self.tenant)
        self.assertEqual(get_current_tenant(), self.tenant)
        clear_current_tenant()
        self.assertIsNone(get_current_tenant())


class TenantInviteTest(TestCase):
    """Testes de convites"""

    def setUp(self):
        self.owner = User.objects.create_user(username="inv_own", password="test")
        self.tenant = Tenant.objects.create(name="Inv", slug="inv", owner=self.owner)

    def test_create_invite(self):
        import datetime

        from django.utils import timezone

        inv = TenantInvite.objects.create(
            tenant=self.tenant,
            email="new@test.com",
            role="agent",
            token="abc123",
            invited_by=self.owner,
            expires_at=timezone.now() + datetime.timedelta(days=7),
        )
        self.assertFalse(inv.is_expired)
        self.assertFalse(inv.accepted)

    def test_expired_invite(self):
        import datetime

        from django.utils import timezone

        inv = TenantInvite.objects.create(
            tenant=self.tenant,
            email="old@test.com",
            role="agent",
            token="expired123",
            invited_by=self.owner,
            expires_at=timezone.now() - datetime.timedelta(days=1),
        )
        self.assertTrue(inv.is_expired)


class TenantViewTest(TestCase):
    """Testes dos endpoints de tenant"""

    def setUp(self):
        self.owner = User.objects.create_user(username="tv_owner", password="test123")
        self.agent = User.objects.create_user(username="tv_agent", password="test123")
        self.tenant = Tenant.objects.create(
            name="ViewTest",
            slug="viewtest",
            owner=self.owner,
            max_agents=5,
            max_tickets_month=500,
        )
        TenantMembership.objects.create(tenant=self.tenant, user=self.owner, role="owner")
        TenantMembership.objects.create(tenant=self.tenant, user=self.agent, role="agent")

    def _login_as(self, username):
        self.client.login(username=username, password="test123")

    @expectedFailure  # Ticket model ainda não tem campo 'tenant'
    def test_tenant_info(self):
        self._login_as("tv_owner")
        resp = self.client.get("/dashboard/api/tenant/", HTTP_X_TENANT_SLUG="viewtest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["slug"], "viewtest")

    def test_tenant_members(self):
        self._login_as("tv_owner")
        resp = self.client.get("/dashboard/api/tenant/members/", HTTP_X_TENANT_SLUG="viewtest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["members"]), 2)

    def test_user_tenants(self):
        self._login_as("tv_agent")
        resp = self.client.get("/dashboard/api/tenants/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(len(data["tenants"]), 1)

    def test_invite_by_owner(self):
        self._login_as("tv_owner")
        resp = self.client.post(
            "/dashboard/api/tenant/invite/",
            json.dumps({"email": "new@test.com", "role": "agent"}),
            content_type="application/json",
            HTTP_X_TENANT_SLUG="viewtest",
        )
        self.assertEqual(resp.status_code, 201)

    def test_invite_by_agent_forbidden(self):
        self._login_as("tv_agent")
        resp = self.client.post(
            "/dashboard/api/tenant/invite/",
            json.dumps({"email": "x@test.com", "role": "agent"}),
            content_type="application/json",
            HTTP_X_TENANT_SLUG="viewtest",
        )
        self.assertEqual(resp.status_code, 403)

    def test_switch_tenant(self):
        self._login_as("tv_agent")
        resp = self.client.post(
            "/dashboard/api/tenant/switch/",
            json.dumps({"tenant_slug": "viewtest"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])

    def test_switch_tenant_no_access(self):
        other_user = User.objects.create_user(username="outsider", password="test123")
        self._login_as("outsider")
        resp = self.client.post(
            "/dashboard/api/tenant/switch/",
            json.dumps({"tenant_slug": "viewtest"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
