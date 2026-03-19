from datetime import timedelta
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone

from church.forms import ChurchInvitationForm, ChurchMembershipAssignForm
from church.limits import (
    enforce_limits_for_model,
    filter_messages_for_retention,
    filter_notifications_for_retention,
)
from church.models import (
    ChurchInvitation,
    ChurchMembership,
    ContactMessage,
    Notification,
    Page,
    Sermon,
)

from .helpers import ChurchTestCase


class PlanLimitEnforcementTests(ChurchTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="plan-admin", email="plan-admin@example.com")
        self.extra_user = self.create_user(username="plan-user", email="plan-user@example.com")
        self.church = self.create_church(
            name="Plan Church",
            max_sermons_override=1,
            max_pages_override=1,
            max_users_override=1,
            max_pending_invitations_override=1,
            message_retention_days_override=30,
            notification_retention_days_override=15,
        )
        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)

    def test_sermon_limit_blocks_second_sermon(self):
        Sermon.objects.create(
            church=self.church,
            title="Premier sermon",
            created_by=self.admin,
        )

        with self.assertRaises(ValidationError):
            enforce_limits_for_model(self.church, Sermon)

    def test_page_limit_blocks_second_page(self):
        Page.objects.create(
            church=self.church,
            title="Premiere page",
            created_by=self.admin,
        )

        with self.assertRaises(ValidationError):
            enforce_limits_for_model(self.church, Page)

    def test_user_limit_blocks_membership_assignment(self):
        form = ChurchMembershipAssignForm(
            data={
                "identifier": self.extra_user.username,
                "role": ChurchMembership.Role.STAFF,
            },
            church=self.church,
        )
        self.assertTrue(form.is_valid(), form.errors)

        with self.assertRaises(ValidationError):
            form.save(self.church)

    def test_pending_invitation_limit_blocks_second_pending_invitation(self):
        ChurchInvitation.objects.create(
            church=self.church,
            email="first-invite@example.com",
            role=ChurchMembership.Role.STAFF,
            invited_by=self.admin,
        )
        form = ChurchInvitationForm(
            data={
                "email": "second-invite@example.com",
                "role": ChurchMembership.Role.SECRETARY,
            },
            church=self.church,
            invited_by=self.admin,
        )
        self.assertTrue(form.is_valid(), form.errors)

        with self.assertRaises(ValidationError):
            form.save()

    def test_retention_filters_old_notifications_and_resolved_messages(self):
        old_notification = Notification.objects.create(
            church=self.church,
            recipient=self.admin,
            category=Notification.Category.EVENT,
            title="Ancienne notification",
            is_read=False,
        )
        fresh_notification = Notification.objects.create(
            church=self.church,
            recipient=self.admin,
            category=Notification.Category.EVENT,
            title="Notification recente",
            is_read=False,
        )
        Notification.objects.filter(pk=old_notification.pk).update(
            created_at=timezone.now() - timedelta(days=20)
        )

        old_archived_message = ContactMessage.objects.create(
            church=self.church,
            sender_name="Ancien contact",
            sender_email="ancien@example.com",
            subject="Archive",
            message="Archive",
            status=ContactMessage.Status.ARCHIVED,
        )
        old_open_message = ContactMessage.objects.create(
            church=self.church,
            sender_name="Ancien ouvert",
            sender_email="ouvert@example.com",
            subject="Ouvert",
            message="Ouvert",
            status=ContactMessage.Status.NEW,
        )
        ContactMessage.objects.filter(pk=old_archived_message.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        ContactMessage.objects.filter(pk=old_open_message.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )

        retained_notifications = filter_notifications_for_retention(
            Notification.objects.filter(recipient=self.admin),
            [self.church],
        )
        retained_messages = filter_messages_for_retention(
            ContactMessage.objects.filter(church=self.church),
            self.church,
        )

        self.assertIn(fresh_notification, retained_notifications)
        self.assertNotIn(old_notification, retained_notifications)
        self.assertNotIn(old_archived_message, retained_messages)
        self.assertIn(old_open_message, retained_messages)

    def test_prune_plan_activity_deletes_expired_notifications_and_archived_messages(self):
        old_notification = Notification.objects.create(
            church=self.church,
            recipient=self.admin,
            category=Notification.Category.EVENT,
            title="Ancienne notification",
        )
        old_archived_message = ContactMessage.objects.create(
            church=self.church,
            sender_name="Ancien contact",
            sender_email="ancien@example.com",
            subject="Archive",
            message="Archive",
            status=ContactMessage.Status.ARCHIVED,
        )
        old_open_message = ContactMessage.objects.create(
            church=self.church,
            sender_name="Toujours ouvert",
            sender_email="ouvert@example.com",
            subject="Ouvert",
            message="Ouvert",
            status=ContactMessage.Status.NEW,
        )
        Notification.objects.filter(pk=old_notification.pk).update(
            created_at=timezone.now() - timedelta(days=20)
        )
        ContactMessage.objects.filter(pk=old_archived_message.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        ContactMessage.objects.filter(pk=old_open_message.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )

        call_command("prune_plan_activity", stdout=StringIO())

        self.assertFalse(Notification.objects.filter(pk=old_notification.pk).exists())
        self.assertFalse(ContactMessage.objects.filter(pk=old_archived_message.pk).exists())
        self.assertTrue(ContactMessage.objects.filter(pk=old_open_message.pk).exists())

