from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ChurchInvitationForm
from .models import Church, ChurchInvitation, ChurchMembership
from .permissions import (
    CAP_MANAGE_EVENTS,
    CAP_SWITCH_CHURCH,
    CAP_VIEW_AUDIT,
    get_churches_for_capability,
    user_has_any_capability,
)


TEST_STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@override_settings(STORAGES=TEST_STORAGES)
class SingleChurchMembershipPolicyTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username="member",
            email="member@example.com",
            password="StrongPass123!",
        )
        self.church_one = Church.objects.create(name="Alpha Church")
        self.church_two = Church.objects.create(name="Beta Church")

    def test_non_superuser_cannot_have_two_active_memberships(self):
        ChurchMembership.objects.create(
            user=self.user,
            church=self.church_one,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            ChurchMembership.objects.create(
                user=self.user,
                church=self.church_two,
                role=ChurchMembership.Role.STAFF,
                is_active=True,
            )

    def test_invitation_form_rejects_existing_user_from_another_church(self):
        ChurchMembership.objects.create(
            user=self.user,
            church=self.church_one,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )

        form = ChurchInvitationForm(
            data={
                "email": self.user.email,
                "role": ChurchMembership.Role.STAFF,
            },
            church=self.church_two,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("une seule eglise active", str(form.errors).lower())

    def test_accept_invite_rejects_user_with_other_active_membership(self):
        ChurchMembership.objects.create(
            user=self.user,
            church=self.church_one,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )
        invite = ChurchInvitation.objects.create(
            church=self.church_two,
            email=self.user.email,
            role=ChurchMembership.Role.STAFF,
            invited_by=self.user,
        )

        self.client.force_login(self.user)
        response = self.client.post(reverse("accept_invite", args=[invite.token]))

        self.assertRedirects(
            response,
            reverse("pending_invitations"),
            fetch_redirect_response=False,
        )
        self.assertFalse(
            ChurchMembership.objects.filter(
                user=self.user,
                church=self.church_two,
                is_active=True,
            ).exists()
        )
        invite.refresh_from_db()
        self.assertEqual(invite.status, ChurchInvitation.Status.PENDING)


@override_settings(STORAGES=TEST_STORAGES)
class TenantLoginFlowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.password = "StrongPass123!"

    def test_single_church_user_redirects_to_dashboard(self):
        user = self.user_model.objects.create_user(
            username="single",
            email="single@example.com",
            password=self.password,
        )
        church = Church.objects.create(name="Single Church")
        ChurchMembership.objects.create(
            user=user,
            church=church,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.session.get("active_church_id"), church.id)

    def test_multi_church_non_superuser_is_redirected_home(self):
        user = self.user_model.objects.create_user(
            username="conflict",
            email="conflict@example.com",
            password=self.password,
        )
        church_one = Church.objects.create(name="Conflict One")
        church_two = Church.objects.create(name="Conflict Two")
        now = timezone.now()
        ChurchMembership.objects.bulk_create(
            [
                ChurchMembership(
                    user=user,
                    church=church_one,
                    role=ChurchMembership.Role.ADMIN,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                ChurchMembership(
                    user=user,
                    church=church_two,
                    role=ChurchMembership.Role.STAFF,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(
            response,
            reverse("home"),
            fetch_redirect_response=False,
        )
        self.assertIsNone(self.client.session.get("active_church_id"))

    def test_user_with_pending_invitation_is_redirected_to_invitation_inbox(self):
        user = self.user_model.objects.create_user(
            username="invitee",
            email="invitee@example.com",
            password=self.password,
        )
        church = Church.objects.create(name="Invite Church")
        ChurchInvitation.objects.create(
            church=church,
            email=user.email,
            role=ChurchMembership.Role.STAFF,
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(
            response,
            reverse("pending_invitations"),
            fetch_redirect_response=False,
        )

    def test_user_without_church_and_without_invitation_is_logged_out(self):
        user = self.user_model.objects.create_user(
            username="orphan",
            email="orphan@example.com",
            password=self.password,
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(
            response,
            reverse("home"),
            fetch_redirect_response=False,
        )
        self.assertIsNone(self.client.session.get("_auth_user_id"))


@override_settings(STORAGES=TEST_STORAGES)
class PendingInvitationWorkflowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username="pending",
            email="pending@example.com",
            password="StrongPass123!",
        )
        self.church = Church.objects.create(name="Pending Church")
        self.invite = ChurchInvitation.objects.create(
            church=self.church,
            email=self.user.email,
            role=ChurchMembership.Role.SECRETARY,
        )

    def test_pending_invitations_page_lists_matching_invites(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("pending_invitations"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.church.name)

    def test_decline_invite_marks_invitation_declined(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("decline_invite", args=[self.invite.token]))

        self.assertRedirects(
            response,
            reverse("home"),
            fetch_redirect_response=False,
        )
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, ChurchInvitation.Status.DECLINED)
        self.assertIsNotNone(self.invite.declined_at)
        self.assertIsNone(self.client.session.get("_auth_user_id"))


@override_settings(STORAGES=TEST_STORAGES)
class CapabilityConsistencyTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.admin_user = self.user_model.objects.create_user(
            username="audit-admin",
            email="audit-admin@example.com",
            password="StrongPass123!",
        )
        self.staff_user = self.user_model.objects.create_user(
            username="audit-staff",
            email="audit-staff@example.com",
            password="StrongPass123!",
        )
        self.superuser = self.user_model.objects.create_superuser(
            username="platform-root",
            email="root@example.com",
            password="StrongPass123!",
        )
        self.church_one = Church.objects.create(name="Audit Church")
        self.church_two = Church.objects.create(name="Second Audit Church")
        ChurchMembership.objects.create(
            user=self.admin_user,
            church=self.church_one,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )
        ChurchMembership.objects.create(
            user=self.staff_user,
            church=self.church_one,
            role=ChurchMembership.Role.STAFF,
            is_active=True,
        )

    def test_admin_capability_helpers_match_audit_access(self):
        self.assertTrue(user_has_any_capability(self.admin_user, CAP_VIEW_AUDIT))
        self.assertEqual(
            list(get_churches_for_capability(self.admin_user, CAP_VIEW_AUDIT)),
            [self.church_one],
        )

    def test_staff_cannot_view_audit_but_keeps_role_capabilities(self):
        self.assertFalse(user_has_any_capability(self.staff_user, CAP_VIEW_AUDIT))
        self.assertTrue(user_has_any_capability(self.staff_user, CAP_MANAGE_EVENTS))
        self.assertFalse(
            get_churches_for_capability(self.staff_user, CAP_VIEW_AUDIT).exists()
        )

    def test_superuser_switch_church_and_audit_helpers_share_same_source(self):
        self.assertTrue(user_has_any_capability(self.superuser, CAP_VIEW_AUDIT))
        self.assertTrue(user_has_any_capability(self.superuser, CAP_SWITCH_CHURCH))

    def test_audit_route_denies_staff_and_allows_admin(self):
        self.client.force_login(self.staff_user)
        staff_response = self.client.get(reverse("manage_audit_logs"))
        self.assertRedirects(
            staff_response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )

        self.client.force_login(self.admin_user)
        self.client.session["active_church_id"] = self.church_one.id
        self.client.session.save()
        admin_response = self.client.get(reverse("manage_audit_logs"))
        self.assertEqual(admin_response.status_code, 200)
