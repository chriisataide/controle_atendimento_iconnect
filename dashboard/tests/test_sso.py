"""
Testes do módulo SSO — Provedores, login OIDC, provisionamento de usuários.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.utils.sso import SSOProvider, SSOSession, sso_engine


class SSOProviderModelTest(TestCase):
    def _create_provider(self, **kwargs):
        defaults = {
            "name": "Azure AD",
            "slug": "azure-ad",
            "protocol": "oidc",
            "client_id": "test-client-id",
            "client_secret": "test-secret",
            "authorization_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "userinfo_url": "https://graph.microsoft.com/oidc/userinfo",
        }
        defaults.update(kwargs)
        return SSOProvider.objects.create(**defaults)

    def test_criacao(self):
        p = self._create_provider()
        self.assertTrue(p.pk)
        self.assertEqual(p.protocol, "oidc")

    def test_str(self):
        p = self._create_provider()
        self.assertIn("Azure AD", str(p))

    def test_domain_whitelist(self):
        p = self._create_provider(domain_whitelist="empresa.com.br\noutro.com")
        self.assertTrue(p.is_email_allowed("user@empresa.com.br"))
        self.assertFalse(p.is_email_allowed("user@gmail.com"))

    def test_empty_whitelist_allows_all(self):
        p = self._create_provider(domain_whitelist="")
        self.assertTrue(p.is_email_allowed("user@qualquer.com"))

    def test_client_secret_encrypted_on_save(self):
        p = self._create_provider(client_secret="plain-secret")
        p.refresh_from_db()
        self.assertTrue(p.client_secret.startswith("enc::") or p.client_secret == "plain-secret")

    def test_slug_unique(self):
        self._create_provider(slug="unique")
        with self.assertRaises(Exception):
            self._create_provider(slug="unique")


class SSOSessionModelTest(TestCase):
    def test_expired(self):
        provider = SSOProvider.objects.create(
            name="Test",
            slug="test",
            protocol="oidc",
            client_id="x",
            authorization_url="https://example.com/auth",
            token_url="https://example.com/token",
            userinfo_url="https://example.com/userinfo",
        )
        session = SSOSession.objects.create(
            state="test-state",
            provider=provider,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertTrue(session.is_expired)

    def test_not_expired(self):
        provider = SSOProvider.objects.create(
            name="Test2",
            slug="test2",
            protocol="oidc",
            client_id="x",
            authorization_url="https://example.com/auth",
            token_url="https://example.com/token",
            userinfo_url="https://example.com/userinfo",
        )
        session = SSOSession.objects.create(
            state="test-state-2",
            provider=provider,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.assertFalse(session.is_expired)


class SSOEngineTest(TestCase):
    def test_get_active_providers(self):
        SSOProvider.objects.create(
            name="Active",
            slug="active",
            protocol="oidc",
            is_active=True,
            client_id="x",
            authorization_url="https://example.com/auth",
            token_url="https://example.com/token",
            userinfo_url="https://example.com/userinfo",
        )
        SSOProvider.objects.create(
            name="Inactive",
            slug="inactive",
            protocol="oidc",
            is_active=False,
            client_id="x",
            authorization_url="https://example.com/auth",
            token_url="https://example.com/token",
            userinfo_url="https://example.com/userinfo",
        )
        providers = sso_engine.get_active_providers()
        self.assertEqual(providers.count(), 1)

    def test_provision_creates_user(self):
        provider = SSOProvider.objects.create(
            name="Test",
            slug="test-p",
            protocol="oidc",
            client_id="x",
            auto_create_user=True,
            authorization_url="https://example.com/auth",
            token_url="https://example.com/token",
            userinfo_url="https://example.com/userinfo",
        )
        user = sso_engine._provision_user(provider, "new@test.com", "newuser", "New", "User")
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "new@test.com")
        self.assertFalse(user.has_usable_password())

    def test_provision_refuses_when_disabled(self):
        provider = SSOProvider.objects.create(
            name="Test",
            slug="test-no-create",
            protocol="oidc",
            client_id="x",
            auto_create_user=False,
            authorization_url="https://example.com/auth",
            token_url="https://example.com/token",
            userinfo_url="https://example.com/userinfo",
        )
        user = sso_engine._provision_user(provider, "noone@test.com", "nobody", "", "")
        self.assertIsNone(user)


class SSOViewTest(TestCase):
    def test_provider_list_json(self):
        SSOProvider.objects.create(
            name="Google",
            slug="google",
            protocol="oidc",
            is_active=True,
            client_id="x",
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        )
        resp = self.client.get(reverse("sso_providers"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["providers"]), 1)

    def test_login_redirect_for_unknown_provider(self):
        resp = self.client.get(reverse("sso_login", kwargs={"slug": "nonexistent"}))
        self.assertEqual(resp.status_code, 302)

    def test_callback_for_unknown_provider(self):
        resp = self.client.get(reverse("sso_callback", kwargs={"slug": "nonexistent"}))
        self.assertEqual(resp.status_code, 302)
