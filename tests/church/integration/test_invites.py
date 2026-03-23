from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from django.urls import reverse

from church.models import AuditLog, ChurchInvitation, ChurchMembership, Notification
from tests.factories import SaaSTestCase


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="tests@example.com")
class InvitationIntegrationTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="invite-admin", email="invite-admin@example.com")
        self.invited_user = self.create_user(username="invite-target", email="invite-target@example.com")
        self.church = self.create_church(name="Invite Church")
        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)
        self.login_to_church(self.admin, self.church)

    def test_invite_user_creates_invitation_notifications_email_and_audit(self):
        response = self.client.post(
            reverse("invite_user"),
            {
                "email": self.invited_user.email,
                "role": ChurchMembership.Role.SECRETARY,
            },
        )

        invite = ChurchInvitation.objects.get(email=self.invited_user.email)
        self.assertRedirects(response, reverse("manage_users"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(AuditLog.objects.filter(church=self.church, action="invite_create").exists())
        self.assertTrue(Notification.objects.filter(church=self.church, recipient=self.invited_user).exists())
        self.assertEqual(invite.role, ChurchMembership.Role.SECRETARY)

    def test_revoke_invite_updates_status_and_marks_related_notifications_read(self):
        invite = self.create_invitation(
            self.church,
            self.invited_user.email,
            invited_by=self.admin,
        )
        Notification.objects.create(
            church=self.church,
            recipient=self.invited_user,
            category=Notification.Category.INVITE,
            title="Invitation ? rejoindre l'?glise",
            link=reverse("accept_invite", args=[invite.token]),
            is_read=False,
        )

        response = self.client.post(reverse("revoke_invite", args=[invite.pk]))

        invite.refresh_from_db()
        self.assertRedirects(response, reverse("manage_users"))
        self.assertEqual(invite.status, ChurchInvitation.Status.REVOKED)
        self.assertFalse(Notification.objects.filter(recipient=self.invited_user, is_read=False).exists())

    def test_resend_invite_sends_email_and_extends_expiry(self):
        invite = self.create_invitation(
            self.church,
            self.invited_user.email,
            invited_by=self.admin,
        )
        old_expiry = invite.expires_at

        response = self.client.post(reverse("resend_invite", args=[invite.pk]))

        invite.refresh_from_db()
        self.assertRedirects(response, reverse("manage_users"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertGreater(invite.expires_at, old_expiry)

    def test_resend_invite_handles_email_failure_gracefully(self):
        invite = self.create_invitation(
            self.church,
            self.invited_user.email,
            invited_by=self.admin,
        )

        with patch("church.views._send_invite_email", side_effect=RuntimeError("smtp down")):
            response = self.client.post(reverse("resend_invite", args=[invite.pk]), follow=True)

        self.assertEqual(response.status_code, 200)

    def test_manage_users_get_does_not_mutate_expired_invitation_status(self):
        invite = self.create_invitation(
            self.church,
            "expired@example.com",
            invited_by=self.admin,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        response = self.client.get(reverse("manage_users"))

        invite.refresh_from_db()
        self.assertEqual(invite.status, ChurchInvitation.Status.PENDING)
        self.assertContains(response, "Utilisateurs")
        self.assertNotContains(response, invite.email)

    def test_expired_pending_invitation_does_not_block_new_invite_for_same_email(self):
        self.create_invitation(
            self.church,
            self.invited_user.email,
            invited_by=self.admin,
            expires_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.post(
            reverse("invite_user"),
            {
                "email": self.invited_user.email,
                "role": ChurchMembership.Role.SECRETARY,
            },
        )

        self.assertRedirects(response, reverse("manage_users"))
        self.assertEqual(
            ChurchInvitation.objects.filter(church=self.church, email=self.invited_user.email).count(),
            2,
        )
        self.assertTrue(
            ChurchInvitation.objects.filter(
                church=self.church,
                email=self.invited_user.email,
                status=ChurchInvitation.Status.PENDING,
                expires_at__gt=timezone.now(),
            ).exists()
        )

    def test_decline_invite_requires_post(self):
        self.client.logout()
        invite = self.create_invitation(
            self.church,
            self.invited_user.email,
            invited_by=self.admin,
        )
        self.client.force_login(self.invited_user)

        response = self.client.get(reverse("decline_invite", args=[invite.token]))

        invite.refresh_from_db()
        self.assertEqual(response.status_code, 405)
        self.assertEqual(invite.status, ChurchInvitation.Status.PENDING)

    def test_accept_invite_creates_membership_and_marks_notifications_read(self):
        self.client.logout()
        invite = self.create_invitation(
            self.church,
            self.invited_user.email,
            role=ChurchMembership.Role.STAFF,
            invited_by=self.admin,
        )
        Notification.objects.create(
            church=self.church,
            recipient=self.invited_user,
            category=Notification.Category.INVITE,
            title="Invitation ? rejoindre l'?glise",
            link=reverse("accept_invite", args=[invite.token]),
            is_read=False,
        )
        self.client.force_login(self.invited_user)

        response = self.client.post(reverse("accept_invite", args=[invite.token]))

        invite.refresh_from_db()
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertEqual(invite.status, ChurchInvitation.Status.ACCEPTED)
        self.assertTrue(ChurchMembership.objects.filter(user=self.invited_user, church=self.church, is_active=True).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.invited_user, is_read=False).exists())

