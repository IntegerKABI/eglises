from django.urls import reverse

from church.models import AuditLog, ChurchMembership, SiteSettings
from tests.factories import SaaSTestCase


class SettingsIntegrationTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="settings-admin")
        self.superuser = self.create_user(username="settings-super", is_superuser=True)
        self.church = self.create_church(name="Settings Church")
        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)

    def test_site_settings_update_creates_platform_audit_log(self):
        self.client.force_login(self.superuser)
        session = self.client.session
        session.pop("active_church_id", None)
        session.save()

        response = self.client.post(
            reverse("site_settings"),
            {
                "site_name": "Nouvelle plateforme",
                "site_slogan": "Slogan",
                "site_description": "Description",
                "contact_email": "support@example.com",
            },
        )

        self.assertRedirects(response, reverse("site_settings"))
        self.assertEqual(SiteSettings.get().site_name, "Nouvelle plateforme")
        self.assertTrue(AuditLog.objects.filter(church__isnull=True, action="settings_update").exists())

