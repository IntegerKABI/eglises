from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from church.models import BackgroundJob, Church, ChurchInvitation, ChurchMembership, ContactMessage, Event, Member, Notification, Page, Sermon
from tests.factories import SaaSTestCase


class ManagementCommandIntegrationTests(SaaSTestCase):
    def test_setup_demo_creates_demo_dataset_and_is_idempotent(self):
        stdout = StringIO()

        call_command("setup_demo", stdout=stdout)

        user_model = get_user_model()
        church = Church.objects.get(slug="demo")
        first_snapshot = {
            "events": Event.objects.filter(church=church).count(),
            "sermons": Sermon.objects.filter(church=church).count(),
            "members": Member.objects.filter(church=church).count(),
            "pages": Page.objects.filter(church=church).count(),
        }

        self.assertTrue(user_model.objects.filter(username="admin", is_superuser=True).exists())
        self.assertTrue(
            ChurchMembership.objects.filter(
                user__username="admin",
                church=church,
                role=ChurchMembership.Role.ADMIN,
                is_active=True,
            ).exists()
        )
        self.assertEqual(first_snapshot, {"events": 3, "sermons": 3, "members": 5, "pages": 2})

        second_stdout = StringIO()
        call_command("setup_demo", stdout=second_stdout)

        second_snapshot = {
            "events": Event.objects.filter(church=church).count(),
            "sermons": Sermon.objects.filter(church=church).count(),
            "members": Member.objects.filter(church=church).count(),
            "pages": Page.objects.filter(church=church).count(),
        }
        self.assertEqual(second_snapshot, first_snapshot)
        self.assertIn("Installation terminee", second_stdout.getvalue())

    def test_prune_plan_activity_removes_only_expired_records(self):
        church = self.create_church(
            name="Retention Church",
            message_retention_days_override=7,
            notification_retention_days_override=7,
        )
        old_notification = self.create_notification(church, self.create_user(username="notif-recipient"))
        fresh_notification = self.create_notification(church, self.create_user(username="fresh-recipient"), title="Fresh")
        old_notification.created_at = timezone.now() - timedelta(days=10)
        old_notification.save(update_fields=["created_at"])

        old_archived = self.create_message(church, subject="Archived", status=ContactMessage.Status.ARCHIVED)
        old_archived.created_at = timezone.now() - timedelta(days=10)
        old_archived.save(update_fields=["created_at"])

        old_responded = self.create_message(church, subject="Responded", status=ContactMessage.Status.RESPONDED)
        old_responded.created_at = timezone.now() - timedelta(days=10)
        old_responded.save(update_fields=["created_at"])

        old_read = self.create_message(church, subject="Read", status=ContactMessage.Status.READ)
        old_read.created_at = timezone.now() - timedelta(days=10)
        old_read.save(update_fields=["created_at"])

        recent_archived = self.create_message(church, subject="Recent archived", status=ContactMessage.Status.ARCHIVED)

        stdout = StringIO()
        call_command("prune_plan_activity", stdout=stdout)

        self.assertFalse(Notification.objects.filter(pk=old_notification.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=fresh_notification.pk).exists())
        self.assertFalse(ContactMessage.objects.filter(pk=old_archived.pk).exists())
        self.assertFalse(ContactMessage.objects.filter(pk=old_responded.pk).exists())
        self.assertTrue(ContactMessage.objects.filter(pk=old_read.pk).exists())
        self.assertTrue(ContactMessage.objects.filter(pk=recent_archived.pk).exists())
        self.assertIn("Retention Church", stdout.getvalue())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="tests@example.com",
        BACKGROUND_JOBS_EAGER=False,
    )
    def test_process_background_jobs_delivers_pending_invite_emails(self):
        admin = self.create_user(username="job-admin", email="job-admin@example.com")
        recipient = self.create_user(username="job-user", email="job-user@example.com")
        church = self.create_church(name="Job Church")
        self.add_membership(admin, church, role=ChurchMembership.Role.ADMIN)
        invitation = self.create_invitation(
            church,
            recipient.email,
            invited_by=admin,
        )
        BackgroundJob.objects.create(
            job_type=BackgroundJob.JobType.SEND_INVITE_EMAIL,
            payload={
                "invitation_id": invitation.pk,
                "invite_url": f"http://testserver/invitations/{invitation.token}/",
            },
        )

        stdout = StringIO()
        call_command("process_background_jobs", stdout=stdout)

        job = BackgroundJob.objects.get()
        self.assertEqual(job.status, BackgroundJob.Status.COMPLETED)
        self.assertIn("Processed 1 background job", stdout.getvalue())

    @override_settings(BACKGROUND_JOBS_EAGER=False)
    def test_process_background_jobs_marks_failed_delivery_for_retry(self):
        admin = self.create_user(username="retry-admin", email="retry-admin@example.com")
        recipient = self.create_user(username="retry-user", email="retry-user@example.com")
        church = self.create_church(name="Retry Church")
        self.add_membership(admin, church, role=ChurchMembership.Role.ADMIN)
        invitation = self.create_invitation(
            church,
            recipient.email,
            invited_by=admin,
        )
        job = BackgroundJob.objects.create(
            job_type=BackgroundJob.JobType.SEND_INVITE_EMAIL,
            payload={
                "invitation_id": invitation.pk,
                "invite_url": f"http://testserver/invitations/{invitation.token}/",
            },
        )

        with patch("church.background_jobs.send_mail", side_effect=RuntimeError("smtp down")):
            call_command("process_background_jobs", stdout=StringIO())

        job.refresh_from_db()
        self.assertEqual(job.status, BackgroundJob.Status.PENDING)
        self.assertEqual(job.attempts, 1)
        self.assertIn("smtp down", job.last_error)
