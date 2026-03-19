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
