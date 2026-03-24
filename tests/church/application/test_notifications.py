from django.urls import reverse

from church.models import ChurchMembership, Notification
from tests.factories import SaaSTestCase


class NotificationApplicationTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="notif-app-admin")
        self.superuser = self.create_user(username="notif-app-super", is_superuser=True)
        self.church = self.create_church(name="App Notify Church")
        self.other_church = self.create_church(name="App Notify Other")
        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)
        self.login_to_church(self.admin, self.church)

    def test_open_notification_marks_read_and_redirects(self):
        notification = self.create_notification(
            self.church,
            self.admin,
            link=reverse("manage_notifications"),
        )

        response = self.client.get(reverse("open_notification", args=[notification.pk]))

        self.assertRedirects(response, reverse("manage_notifications"), fetch_redirect_response=False)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_superadmin_sees_notifications_across_accessible_churches(self):
        self.create_notification(self.church, self.superuser, title="Church one")
        self.create_notification(self.other_church, self.superuser, title="Church two")
        self.client.force_login(self.superuser)
        session = self.client.session
        session["active_church_id"] = self.church.id
        session.save()

        response = self.client.get(reverse("manage_notifications"))

        self.assertContains(response, "Church one")
        self.assertContains(response, "Church two")

    def test_notification_list_does_not_expose_manual_mark_read_action(self):
        self.create_notification(self.church, self.admin, title="Unread notification")

        response = self.client.get(reverse("manage_notifications"))

        self.assertNotContains(response, "Marquer lu")

