from django.urls import reverse
from django.utils import timezone

from church.models import ChurchInvitation, ChurchMembership
from tests.factories import SaaSTestCase


class AuthFlowApplicationTests(SaaSTestCase):
    def test_single_church_user_redirects_to_dashboard(self):
        user = self.create_user(username="single", email="single@example.com")
        church = self.create_church(name="Single Church")
        self.add_membership(user, church)

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertEqual(self.client.session.get("active_church_id"), church.id)

    def test_multi_church_non_superuser_is_redirected_home(self):
        user = self.create_user(username="conflict", email="conflict@example.com")
        church_one = self.create_church(name="Conflict One")
        church_two = self.create_church(name="Conflict Two")
        now = timezone.now()
        ChurchMembership.objects.bulk_create(
            [
                ChurchMembership(user=user, church=church_one, role=ChurchMembership.Role.ADMIN, is_active=True, created_at=now, updated_at=now),
                ChurchMembership(user=user, church=church_two, role=ChurchMembership.Role.STAFF, is_active=True, created_at=now, updated_at=now),
            ]
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_user_with_pending_invitation_is_redirected_to_pending_invitations(self):
        user = self.create_user(username="invitee", email="invitee@example.com")
        church = self.create_church(name="Invite Church")
        self.create_invitation(church, user.email)

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(response, reverse("pending_invitations"), fetch_redirect_response=False)

    def test_user_without_access_is_logged_out(self):
        user = self.create_user(username="orphan", email="orphan@example.com")

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertIsNone(self.client.session.get("_auth_user_id"))

