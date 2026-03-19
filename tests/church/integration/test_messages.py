from django.urls import reverse

from church.models import ChurchMembership, ContactMessage, ContactMessageReply
from tests.factories import SaaSTestCase


class MessageWorkflowIntegrationTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="message-admin")
        self.staff = self.create_user(username="message-staff")
        self.secretary = self.create_user(username="message-secretary")
        self.church = self.create_church(name="Messages Church")
        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)
        self.add_membership(self.staff, self.church, role=ChurchMembership.Role.STAFF)
        self.add_membership(self.secretary, self.church, role=ChurchMembership.Role.SECRETARY)
        self.message = self.create_message(self.church, subject="Urgent", status=ContactMessage.Status.NEW)

    def test_manage_messages_filters_by_status_and_assignment(self):
        self.login_to_church(self.secretary, self.church)
        self.message.assigned_to = self.secretary
        self.message.save(update_fields=["assigned_to"])

        response = self.client.get(reverse("manage_messages"), {"status": "new", "assigned": "me"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Urgent")

    def test_read_message_actions_update_workflow_state(self):
        self.login_to_church(self.secretary, self.church)

        self.client.post(reverse("read_message", args=[self.message.pk]), {"action": "mark_read"})
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, ContactMessage.Status.READ)

        self.client.post(reverse("read_message", args=[self.message.pk]), {"action": "assign_me"})
        self.message.refresh_from_db()
        self.assertEqual(self.message.assigned_to, self.secretary)

        self.client.post(reverse("read_message", args=[self.message.pk]), {"action": "unassign"})
        self.message.refresh_from_db()
        self.assertIsNone(self.message.assigned_to)

        self.client.post(
            reverse("read_message", args=[self.message.pk]),
            {"action": "respond", "body": "R?ponse envoy?e."},
        )
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, ContactMessage.Status.RESPONDED)
        self.assertTrue(ContactMessageReply.objects.filter(message=self.message).exists())

        self.client.post(reverse("read_message", args=[self.message.pk]), {"action": "archive"})
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, ContactMessage.Status.ARCHIVED)

    def test_staff_is_denied_message_management(self):
        self.login_to_church(self.staff, self.church)

        response = self.client.get(reverse("manage_messages"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

