from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from church.context_processors import church_context
from church.limits import filter_notifications_for_retention
from church.models import ChurchMembership, Notification

from .helpers import ChurchTestCase


class NotificationWorkflowTests(ChurchTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user(username="notify-user", email="notify-user@example.com")
        self.other_user = self.create_user(username="notify-other", email="notify-other@example.com")
        self.church = self.create_church(
            name="Notify Church",
            notification_retention_days_override=15,
        )
        self.other_church = self.create_church(name="Other Notify Church")
        self.add_membership(self.user, self.church, role=ChurchMembership.Role.ADMIN)
        self.login_to_church(self.user, self.church)

    def test_open_notification_marks_it_read(self):
        notification = Notification.objects.create(
            church=self.church,
            recipient=self.user,
            category=Notification.Category.EVENT,
            title="Nouvelle notification",
            link=reverse("manage_notifications"),
        )

        response = self.client.get(reverse("open_notification", args=[notification.pk]))

        self.assertRedirects(
            response,
            reverse("manage_notifications"),
            fetch_redirect_response=False,
        )
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_mark_all_notifications_read_updates_visible_notifications(self):
        first = Notification.objects.create(
            church=self.church,
            recipient=self.user,
            category=Notification.Category.EVENT,
            title="Premiere",
        )
        second = Notification.objects.create(
            church=self.church,
            recipient=self.user,
            category=Notification.Category.MESSAGE,
            title="Deuxieme",
        )

        response = self.client.post(reverse("mark_all_notifications_read"))

        self.assertRedirects(
            response,
            reverse("manage_notifications"),
            fetch_redirect_response=False,
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_read)
        self.assertTrue(second.is_read)

    def test_manage_notifications_lists_only_user_notifications_in_accessible_scope(self):
        Notification.objects.create(
            church=self.church,
            recipient=self.user,
            category=Notification.Category.EVENT,
            title="Pour moi",
        )
        Notification.objects.create(
            church=self.church,
            recipient=self.other_user,
            category=Notification.Category.EVENT,
            title="Pour un autre",
        )

        response = self.client.get(reverse("manage_notifications"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pour moi")
        self.assertNotContains(response, "Pour un autre")

    def test_notification_badge_respects_retention_window(self):
        old_notification = Notification.objects.create(
            church=self.church,
            recipient=self.user,
            category=Notification.Category.EVENT,
            title="Ancienne notification",
            is_read=False,
        )
        Notification.objects.create(
            church=self.church,
            recipient=self.user,
            category=Notification.Category.EVENT,
            title="Recente notification",
            is_read=False,
        )
        Notification.objects.filter(pk=old_notification.pk).update(
            created_at=timezone.now() - timedelta(days=20)
        )

        request = self.client.get(reverse("dashboard")).wsgi_request
        request.user = self.user
        request.current_church = self.church
        request.current_membership = ChurchMembership.objects.get(
            user=self.user,
            church=self.church,
        )
        context = church_context(request)

        self.assertEqual(context["unread_notifications_count"], 1)

    def test_filter_notifications_for_retention_excludes_expired_rows(self):
        old_notification = Notification.objects.create(
            church=self.church,
            recipient=self.user,
            category=Notification.Category.EVENT,
            title="Ancienne notification",
        )
        fresh_notification = Notification.objects.create(
            church=self.church,
            recipient=self.user,
            category=Notification.Category.EVENT,
            title="Recente notification",
        )
        Notification.objects.filter(pk=old_notification.pk).update(
            created_at=timezone.now() - timedelta(days=20)
        )

        retained = filter_notifications_for_retention(
            Notification.objects.filter(recipient=self.user),
            [self.church],
        )

        self.assertNotIn(old_notification, retained)
        self.assertIn(fresh_notification, retained)

