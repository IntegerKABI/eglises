from church.models import ChurchMembership, Notification
from church.notifications import (
    notify_church_admins,
    notify_contact_recipients,
    notify_event_recipients,
    notify_message_recipients,
    notify_user_role_change,
    recipients_for_capability,
)
from tests.factories import SaaSTestCase


class NotificationServiceTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.church = self.create_church()
        self.admin = self.create_user(username="notif-admin")
        self.staff = self.create_user(username="notif-staff")
        self.secretary = self.create_user(username="notif-secretary")
        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)
        self.add_membership(self.staff, self.church, role=ChurchMembership.Role.STAFF)
        self.add_membership(self.secretary, self.church, role=ChurchMembership.Role.SECRETARY)

    def test_recipients_for_capability_returns_matching_users(self):
        users = recipients_for_capability(self.church, "manage_messages")

        self.assertEqual({user.pk for user in users}, {self.admin.pk, self.secretary.pk})

    def test_notify_church_admins_targets_only_admins(self):
        notify_church_admins(self.church, Notification.Category.ROLE, "Admin notice")

        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.admin.pk})

    def test_notify_message_recipients_targets_message_capable_roles(self):
        notify_message_recipients(self.church, Notification.Category.MESSAGE, "Message notice")

        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.admin.pk, self.secretary.pk})

    def test_notify_contact_recipients_prefers_secretaries_and_skips_staff(self):
        notify_contact_recipients(
            self.church,
            Notification.Category.MESSAGE,
            "Nouveau message recu",
            body="Visiteur - Demande de priere",
            source_text="Merci de prier pour ma famille.",
        )

        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.secretary.pk})

    def test_notify_contact_recipients_falls_back_to_admins_without_secretary(self):
        ChurchMembership.objects.filter(user=self.secretary, church=self.church).delete()
        Notification.objects.all().delete()

        notify_contact_recipients(
            self.church,
            Notification.Category.MESSAGE,
            "Nouveau message recu",
            body="Visiteur - Demande de priere",
            source_text="Merci de me recontacter.",
        )

        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.admin.pk})

    def test_notify_contact_recipients_escalates_to_admins_for_urgent_messages(self):
        notify_contact_recipients(
            self.church,
            Notification.Category.MESSAGE,
            "Nouveau message recu",
            body="Visiteur - Urgent",
            source_text="Nous avons une urgence familiale.",
        )

        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.admin.pk, self.secretary.pk})

    def test_notify_event_recipients_targets_event_capable_roles(self):
        notify_event_recipients(self.church, Notification.Category.EVENT, "Event notice")

        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.admin.pk, self.staff.pk, self.secretary.pk})

    def test_notify_user_role_change_notifies_target_and_admins(self):
        notify_user_role_change(self.church, self.staff, "Role update", actor=self.secretary)

        recipients = list(Notification.objects.order_by("recipient_id").values_list("recipient_id", flat=True))
        self.assertEqual(recipients, [self.admin.pk, self.staff.pk])
