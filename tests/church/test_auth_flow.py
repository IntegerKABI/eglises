from django.urls import reverse
from django.utils import timezone

from church.models import ChurchInvitation, ChurchMembership

from .helpers import ChurchTestCase


class TenantLoginFlowTests(ChurchTestCase):
    def test_single_church_user_redirects_to_dashboard(self):
        user = self.create_user(username="single", email="single@example.com")
        church = self.create_church(name="Single Church")
        self.add_membership(user, church)

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
        user = self.create_user(username="conflict", email="conflict@example.com")
        church_one = self.create_church(name="Conflict One")
        church_two = self.create_church(name="Conflict Two")
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
        user = self.create_user(username="invitee", email="invitee@example.com")
        church = self.create_church(name="Invite Church")
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
        user = self.create_user(username="orphan", email="orphan@example.com")

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


class PendingInvitationWorkflowTests(ChurchTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user(username="pending", email="pending@example.com")
        self.church = self.create_church(name="Pending Church")
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

    def test_decline_invite_marks_invitation_declined_and_logs_user_out(self):
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

