from django.urls import reverse

from church.models import Church, ChurchMembership
from tests.factories import SaaSTestCase


class MembershipIntegrationTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="membership-admin")
        self.target = self.create_user(username="membership-target", email="membership-target@example.com")
        self.other = self.create_user(username="membership-other", email="membership-other@example.com")
        self.church = self.create_church(name="Membership Church")
        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)
        self.login_to_church(self.admin, self.church)

    def test_add_user_creates_membership(self):
        response = self.client.post(
            reverse("add_user"),
            {
                "username": "new-member",
                "email": "new-member@example.com",
                "first_name": "New",
                "last_name": "Member",
                "phone": "+243810000020",
                "is_active": True,
                "role": ChurchMembership.Role.STAFF,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("manage_users"))
        self.assertTrue(ChurchMembership.objects.filter(church=self.church, user__username="new-member").exists())

    def test_assign_user_creates_membership_for_existing_user(self):
        response = self.client.post(
            reverse("assign_user"),
            {
                "identifier": self.target.username,
                "role": ChurchMembership.Role.SECRETARY,
            },
        )

        self.assertRedirects(response, reverse("manage_users"))
        membership = ChurchMembership.objects.get(user=self.target, church=self.church)
        self.assertEqual(membership.role, ChurchMembership.Role.SECRETARY)

    def test_toggle_membership_deactivates_and_reactivates_user(self):
        membership = self.add_membership(self.target, self.church, role=ChurchMembership.Role.STAFF)

        deactivate_response = self.client.post(
            reverse("toggle_membership", args=[membership.pk]),
            {"action": "deactivate"},
        )
        membership.refresh_from_db()
        self.assertRedirects(deactivate_response, reverse("manage_users"))
        self.assertFalse(membership.is_active)

        activate_response = self.client.post(
            reverse("toggle_membership", args=[membership.pk]),
            {"action": "activate"},
        )
        membership.refresh_from_db()
        self.assertRedirects(activate_response, reverse("manage_users"))
        self.assertTrue(membership.is_active)

    def test_transfer_admin_promotes_target_and_demotes_current_admin(self):
        target_membership = self.add_membership(self.target, self.church, role=ChurchMembership.Role.STAFF)
        current_membership = ChurchMembership.objects.get(user=self.admin, church=self.church)

        response = self.client.post(
            reverse("transfer_admin"),
            {"membership": target_membership.pk},
        )

        current_membership.refresh_from_db()
        target_membership.refresh_from_db()
        self.assertRedirects(response, reverse("manage_users"), fetch_redirect_response=False)
        self.assertEqual(current_membership.role, ChurchMembership.Role.STAFF)
        self.assertEqual(target_membership.role, ChurchMembership.Role.ADMIN)

    def test_transfer_admin_returns_json_for_ajax_requests(self):
        target_membership = self.add_membership(self.target, self.church, role=ChurchMembership.Role.STAFF)

        response = self.client.post(
            reverse("transfer_admin"),
            {"membership": target_membership.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        current_membership = ChurchMembership.objects.get(user=self.admin, church=self.church)
        target_membership.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "success": True,
                "message": "Administrateur transféré.",
                "redirect": reverse("manage_users"),
            },
        )
        self.assertEqual(current_membership.role, ChurchMembership.Role.STAFF)
        self.assertEqual(target_membership.role, ChurchMembership.Role.ADMIN)

    def test_edit_membership_updates_role(self):
        membership = self.add_membership(self.other, self.church, role=ChurchMembership.Role.STAFF)

        response = self.client.post(
            reverse("edit_membership", args=[membership.pk]),
            {"role": ChurchMembership.Role.SECRETARY, "is_active": True},
        )

        membership.refresh_from_db()
        self.assertRedirects(response, reverse("manage_users"))
        self.assertEqual(membership.role, ChurchMembership.Role.SECRETARY)

    def test_toggle_membership_rejects_deactivation_of_last_active_admin(self):
        membership = ChurchMembership.objects.get(user=self.admin, church=self.church)

        response = self.client.post(
            reverse("toggle_membership", args=[membership.pk]),
            {"action": "deactivate"},
            follow=True,
        )

        membership.refresh_from_db()
        self.assertRedirects(response, reverse("manage_users"))
        self.assertTrue(membership.is_active)
        self.assertContains(response, "Au moins un administrateur actif est requis.")

    def test_edit_membership_rejects_demoting_last_active_admin(self):
        membership = ChurchMembership.objects.get(user=self.admin, church=self.church)

        response = self.client.post(
            reverse("edit_membership", args=[membership.pk]),
            {"role": ChurchMembership.Role.STAFF, "is_active": True},
        )

        membership.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(membership.role, ChurchMembership.Role.ADMIN)
        self.assertContains(response, "Au moins un administrateur actif est requis.")

    def test_existing_church_cannot_be_activated_without_an_admin(self):
        superadmin = self.create_user(username="platform-status-admin", is_superuser=True)
        self.client.force_login(superadmin)
        church = self.create_church(name="Inactive Tenant", status=Church.Status.DRAFT)

        response = self.client.post(
            reverse("superadmin_church_status", args=[church.pk]),
            {"status": Church.Status.ACTIVE},
        )

        church.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(church.status, Church.Status.DRAFT)
        self.assertContains(response, "Une eglise active doit avoir au moins un administrateur actif.")

