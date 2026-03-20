from unittest.mock import patch

from django.urls import reverse

from church.models import AuditLog, Church, ChurchMembership
from tests.factories import SaaSTestCase


class SuperAdminChurchManagementIntegrationTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.superuser = self.create_user(username="platform-admin", is_superuser=True)
        self.tenant_admin = self.create_user(
            username="tenant-admin",
            email="tenant-admin@example.com",
        )
        self.managed_church = self.create_church(name="Managed Church")
        self.add_membership(self.tenant_admin, self.managed_church, role=ChurchMembership.Role.ADMIN)

    def _church_create_payload(self, **overrides):
        payload = {
            "name": "Grace Kin",
            "status": Church.Status.ACTIVE,
            "plan": Church.Plan.GROWTH,
            "country": "RD Congo",
            "primary_color": "#2c3e50",
            "secondary_color": "#3498db",
            "admin_assignment_mode": "existing",
        }
        payload.update(overrides)
        return payload

    def test_superadmin_can_create_tenant_with_existing_admin(self):
        self.client.force_login(self.superuser)
        candidate = self.create_user(
            username="candidate-admin",
            email="candidate-admin@example.com",
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("superadmin_church_create"),
                self._church_create_payload(existing_admin_identifier=candidate.email),
            )

        church = Church.objects.get(name="Grace Kin")
        self.assertRedirects(response, reverse("superadmin_church_detail", args=[church.pk]))
        self.assertTrue(
            ChurchMembership.objects.filter(
                user=candidate,
                church=church,
                role=ChurchMembership.Role.ADMIN,
                is_active=True,
            ).exists()
        )
        self.assertTrue(AuditLog.objects.filter(church=church, action="tenant_create").exists())
        self.assertTrue(AuditLog.objects.filter(church=church, action="tenant_assign_admin").exists())

    def test_superadmin_create_rejects_existing_user_from_another_church(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("superadmin_church_create"),
            self._church_create_payload(existing_admin_identifier=self.tenant_admin.email),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "une seule eglise active", status_code=200, html=False)
        self.assertFalse(Church.objects.filter(name="Grace Kin").exists())

    def test_superadmin_can_create_tenant_with_new_admin(self):
        self.client.force_login(self.superuser)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("superadmin_church_create"),
                self._church_create_payload(
                    name="Grace Lubumbashi",
                    admin_assignment_mode="new",
                    new_admin_username="grace-admin",
                    new_admin_email="grace-admin@example.com",
                    new_admin_first_name="Grace",
                    new_admin_last_name="Admin",
                    new_admin_password1=self.password,
                    new_admin_password2=self.password,
                ),
            )

        church = Church.objects.get(name="Grace Lubumbashi")
        self.assertRedirects(response, reverse("superadmin_church_detail", args=[church.pk]))
        self.assertTrue(
            ChurchMembership.objects.filter(
                church=church,
                role=ChurchMembership.Role.ADMIN,
                is_active=True,
                user__username="grace-admin",
            ).exists()
        )

    def test_superadmin_create_flow_rolls_back_on_membership_failure(self):
        self.client.force_login(self.superuser)

        with patch("church.forms.ChurchMembership.objects.create", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("superadmin_church_create"),
                    self._church_create_payload(
                        name="Rollback Church",
                        admin_assignment_mode="new",
                        new_admin_username="rollback-admin",
                        new_admin_email="rollback-admin@example.com",
                        new_admin_password1=self.password,
                        new_admin_password2=self.password,
                    ),
                )

        self.assertFalse(Church.objects.filter(name="Rollback Church").exists())

    def test_superadmin_can_update_tenant_profile(self):
        self.client.force_login(self.superuser)
        church = self.create_church(name="Profile Church", city="Kinshasa")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("superadmin_church_edit", args=[church.pk]),
                {
                    "name": "Profile Church Updated",
                    "description": "Description",
                    "address": "Commune de Gombe",
                    "city": "Lubumbashi",
                    "country": "RD Congo",
                    "phone": "+243900000000",
                    "email": "profile@example.com",
                    "facebook": "",
                    "youtube": "",
                    "instagram": "",
                    "primary_color": "#111111",
                    "secondary_color": "#222222",
                    "welcome_message": "Bienvenue",
                    "service_times": "Dimanche 9h",
                    "pastor_name": "Pasteur Test",
                },
            )

        church.refresh_from_db()
        self.assertRedirects(response, reverse("superadmin_church_detail", args=[church.pk]))
        self.assertEqual(church.city, "Lubumbashi")
        self.assertTrue(AuditLog.objects.filter(church=church, action="tenant_update").exists())

    def test_superadmin_can_update_tenant_plan(self):
        self.client.force_login(self.superuser)
        church = self.create_church(name="Plan Church")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("superadmin_church_plan", args=[church.pk]),
                {
                    "plan": Church.Plan.SCALE,
                    "max_members_override": 300,
                    "max_events_override": 50,
                    "max_sermons_override": 80,
                    "max_pages_override": 20,
                    "max_users_override": 15,
                    "max_pending_invitations_override": 30,
                    "max_storage_mb_override": 2048,
                    "message_retention_days_override": 365,
                    "notification_retention_days_override": 90,
                },
            )

        church.refresh_from_db()
        self.assertRedirects(response, reverse("superadmin_church_detail", args=[church.pk]))
        self.assertEqual(church.plan, Church.Plan.SCALE)
        self.assertEqual(church.max_storage_mb_override, 2048)
        self.assertTrue(AuditLog.objects.filter(church=church, action="tenant_plan_update").exists())

    def test_superadmin_can_update_tenant_status(self):
        self.client.force_login(self.superuser)
        church = self.create_church(name="Lifecycle Church", status=Church.Status.ACTIVE)
        admin = self.create_user(username="life-admin", email="life-admin@example.com")
        self.add_membership(admin, church, role=ChurchMembership.Role.ADMIN)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("superadmin_church_status", args=[church.pk]),
                {"status": Church.Status.SUSPENDED},
            )

        church.refresh_from_db()
        self.assertRedirects(response, reverse("superadmin_church_detail", args=[church.pk]))
        self.assertEqual(church.status, Church.Status.SUSPENDED)
        self.assertFalse(church.is_active)
        self.assertTrue(AuditLog.objects.filter(church=church, action="tenant_status_update").exists())

    def test_superadmin_can_filter_tenant_list(self):
        self.client.force_login(self.superuser)
        active = self.create_church(name="Filtre Active", plan=Church.Plan.STARTER)
        self.create_church(name="Filtre Archivee", plan=Church.Plan.SCALE, status=Church.Status.ARCHIVED)
        admin = self.create_user(username="filter-admin", email="filter-admin@example.com")
        self.add_membership(admin, active, role=ChurchMembership.Role.ADMIN)

        response = self.client.get(
            reverse("superadmin_church_list"),
            {"status": Church.Status.ACTIVE, "plan": Church.Plan.STARTER, "q": admin.email},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Filtre Active")
        self.assertNotContains(response, "Filtre Archivee")

    def test_superadmin_switch_church_sets_session_context(self):
        self.client.force_login(self.superuser)
        church = self.create_church(name="Support Church", status=Church.Status.SUSPENDED)

        response = self.client.post(reverse("superadmin_switch_church", args=[church.pk]))

        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.client.session.get("active_church_id"), church.pk)
