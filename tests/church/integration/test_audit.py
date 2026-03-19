from django.urls import reverse

from church.models import AuditLog, ChurchMembership
from tests.factories import SaaSTestCase


class AuditIntegrationTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="audit-admin-integration")
        self.superuser = self.create_user(username="audit-super", is_superuser=True)
        self.staff = self.create_user(username="audit-staff-integration")
        self.church = self.create_church(name="Audit Integration Church")
        self.other_church = self.create_church(name="Other Audit Church")
        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)
        self.add_membership(self.staff, self.church, role=ChurchMembership.Role.STAFF)

    def test_manage_audit_logs_filters_by_action_for_admin(self):
        self.create_audit_log(self.church, self.admin, action="create", object_repr="Creation visible")
        self.create_audit_log(self.church, self.admin, action="delete", object_repr="Suppression cachee")
        self.login_to_church(self.admin, self.church)

        response = self.client.get(reverse("manage_audit_logs"), {"action": "create"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Creation visible")
        self.assertNotContains(response, "Suppression cachee")

    def test_admin_sees_only_own_church_logs(self):
        self.create_audit_log(self.church, self.admin, action="create", object_repr="Local")
        self.create_audit_log(self.other_church, self.admin, action="create", object_repr="Other")
        self.login_to_church(self.admin, self.church)

        response = self.client.get(reverse("manage_audit_logs"))

        self.assertContains(response, "Local")
        self.assertNotContains(response, "Other")

    def test_superadmin_can_filter_platform_logs(self):
        self.create_audit_log(None, self.superuser, action="settings_update", object_repr="Plateforme")
        self.client.force_login(self.superuser)
        session = self.client.session
        session.pop("active_church_id", None)
        session.save()

        response = self.client.get(reverse("manage_audit_logs"), {"church": "platform"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plateforme")

