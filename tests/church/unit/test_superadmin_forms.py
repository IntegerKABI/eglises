from unittest.mock import patch

from django.contrib.auth import get_user_model

from church.forms import (
    SuperAdminChurchCreateForm,
    SuperAdminChurchPlanForm,
    SuperAdminChurchStatusForm,
)
from church.models import Church, ChurchMembership
from tests.factories import SaaSTestCase


class SuperAdminChurchFormTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()

    def test_create_form_accepts_existing_active_user_without_membership(self):
        candidate = self.create_user(username="tenant-admin", email="tenant-admin@example.com")
        form = SuperAdminChurchCreateForm(
            data={
                "name": "Nouvelle Eglise",
                "status": Church.Status.ACTIVE,
                "plan": Church.Plan.STARTER,
                "admin_assignment_mode": "existing",
                "existing_admin_identifier": candidate.email,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        church = form.save()

        self.assertEqual(church.status, Church.Status.ACTIVE)
        membership = ChurchMembership.objects.get(church=church, user=candidate)
        self.assertEqual(membership.role, ChurchMembership.Role.ADMIN)

    def test_create_form_rejects_existing_user_with_other_active_membership(self):
        candidate = self.create_user(username="occupied-admin", email="occupied-admin@example.com")
        other_church = self.create_church(name="Occupee")
        self.add_membership(candidate, other_church, role=ChurchMembership.Role.ADMIN)

        form = SuperAdminChurchCreateForm(
            data={
                "name": "Nouvelle Eglise",
                "status": Church.Status.DRAFT,
                "plan": Church.Plan.STARTER,
                "admin_assignment_mode": "existing",
                "existing_admin_identifier": candidate.email,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("existing_admin_identifier", form.errors)

    def test_create_form_rejects_superuser_as_tenant_admin(self):
        superuser = self.create_user(
            username="platform-root",
            email="platform-root@example.com",
            is_superuser=True,
        )
        form = SuperAdminChurchCreateForm(
            data={
                "name": "Nouvelle Eglise",
                "status": Church.Status.DRAFT,
                "plan": Church.Plan.STARTER,
                "admin_assignment_mode": "existing",
                "existing_admin_identifier": superuser.email,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("existing_admin_identifier", form.errors)

    def test_create_form_creates_new_admin_user(self):
        form = SuperAdminChurchCreateForm(
            data={
                "name": "Nouvelle Eglise",
                "status": Church.Status.DRAFT,
                "plan": Church.Plan.GROWTH,
                "admin_assignment_mode": "new",
                "new_admin_username": "nouvel-admin",
                "new_admin_email": "nouvel-admin@example.com",
                "new_admin_first_name": "Marie",
                "new_admin_last_name": "Kasongo",
                "new_admin_password1": self.password,
                "new_admin_password2": self.password,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        church = form.save()

        created_user = self.user_model.objects.get(email="nouvel-admin@example.com")
        self.assertTrue(created_user.check_password(self.password))
        self.assertTrue(
            ChurchMembership.objects.filter(
                church=church,
                user=created_user,
                role=ChurchMembership.Role.ADMIN,
                is_active=True,
            ).exists()
        )

    def test_create_form_rolls_back_church_when_membership_creation_fails(self):
        candidate = self.create_user(username="rollback-admin", email="rollback-admin@example.com")
        form = SuperAdminChurchCreateForm(
            data={
                "name": "Rollback Church",
                "status": Church.Status.ACTIVE,
                "plan": Church.Plan.STARTER,
                "admin_assignment_mode": "existing",
                "existing_admin_identifier": candidate.email,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        with patch("church.forms.ChurchMembership.objects.create", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                form.save()

        self.assertFalse(Church.objects.filter(name="Rollback Church").exists())

    def test_status_form_requires_active_admin_before_activation(self):
        church = self.create_church(name="Draft Church", status=Church.Status.DRAFT)
        form = SuperAdminChurchStatusForm(
            data={"status": Church.Status.ACTIVE},
            instance=church,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_plan_form_accepts_override_updates(self):
        church = self.create_church(name="Plan Church", plan=Church.Plan.STARTER)
        form = SuperAdminChurchPlanForm(
            data={
                "plan": Church.Plan.SCALE,
                "max_members_override": 250,
                "max_events_override": 40,
                "max_sermons_override": 50,
                "max_pages_override": 25,
                "max_users_override": 12,
                "max_pending_invitations_override": 15,
                "max_storage_mb_override": 1024,
                "message_retention_days_override": 180,
                "notification_retention_days_override": 45,
            },
            instance=church,
        )

        self.assertTrue(form.is_valid(), form.errors)
