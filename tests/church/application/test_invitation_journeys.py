from django.urls import reverse

from church.models import ChurchInvitation
from tests.factories import SaaSTestCase


class InvitationJourneyApplicationTests(SaaSTestCase):
    def test_pending_invitations_lists_only_the_logged_in_users_invites(self):
        user = self.create_user(username="invite-journey", email="invite-journey@example.com")
        other_user = self.create_user(username="other-invitee", email="other-invitee@example.com")
        church = self.create_church(name="Journey Church")
        visible_invite = self.create_invitation(church, user.email)
        self.create_invitation(church, other_user.email)
        self.client.force_login(user)

        response = self.client.get(reverse("pending_invitations"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, church.name)
        self.assertNotContains(response, other_user.email)

    def test_declining_last_invitation_logs_user_out_and_redirects_home(self):
        user = self.create_user(username="decline-user", email="decline@example.com")
        church = self.create_church(name="Decline Church")
        invite = self.create_invitation(church, user.email)
        self.client.force_login(user)

        response = self.client.post(reverse("decline_invite", args=[invite.token]), follow=True)

        invite.refresh_from_db()
        self.assertEqual(invite.status, ChurchInvitation.Status.DECLINED)
        self.assertRedirects(response, reverse("home"))
        self.assertContains(response, "Invitation refusee")
        self.assertIsNone(self.client.session.get("_auth_user_id"))

    def test_pending_invitations_logs_out_user_without_access_or_invites(self):
        user = self.create_user(username="orphan-journey", email="orphan-journey@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse("pending_invitations"), follow=True)

        self.assertRedirects(response, reverse("home"))
        self.assertContains(response, "aucune invitation en attente")
        self.assertIsNone(self.client.session.get("_auth_user_id"))
