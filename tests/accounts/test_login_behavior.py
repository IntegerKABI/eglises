from django.test import override_settings
from django.urls import reverse

from tests.factories import SaaSTestCase


class TenantLoginViewTests(SaaSTestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connexion")

    def test_invalid_credentials_keep_user_on_login_page(self):
        user = self.create_user(username="bad-login", email="bad-login@example.com")

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mot de passe valides")

    @override_settings(RATE_LIMITS={"login_ip": {"limit": 1, "window": 60}, "login_account": {"limit": 1, "window": 60}})
    def test_login_is_rate_limited_after_repeated_failures(self):
        user = self.create_user(username="limited-login", email="limited-login@example.com")
        self.client.defaults["REMOTE_ADDR"] = "10.0.0.10"

        self.client.post(
            reverse("login"),
            {"username": user.username, "password": "wrong-password"},
        )
        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trop de tentatives")
