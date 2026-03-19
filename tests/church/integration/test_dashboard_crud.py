from django.urls import reverse

from church.models import AuditLog, ChurchMembership, Event, Member, Notification, Page, Sermon
from tests.factories import SaaSTestCase


class DashboardCrudIntegrationTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="dashboard-admin")
        self.church = self.create_church(name="Dashboard Church")
        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)
        self.login_to_church(self.admin, self.church)

    def test_event_crud_creates_notifications_and_audit_logs(self):
        create_response = self.client.post(
            reverse("add_event"),
            {
                "title": "Concert de louange",
                "description": "Soir?e sp?ciale",
                "event_date": "2026-06-15",
                "event_time": "18:00",
                "end_date": "2026-06-15",
                "location": "Temple central",
                "visibility": "public",
                "is_featured": True,
                "is_active": True,
            },
        )
        event = Event.objects.get(title="Concert de louange")
        update_response = self.client.post(
            reverse("edit_event", args=[event.pk]),
            {
                "title": "Concert de louange mis ? jour",
                "description": "Soir?e sp?ciale",
                "event_date": "2026-06-15",
                "event_time": "18:00",
                "end_date": "2026-06-15",
                "location": "Temple central",
                "visibility": "public",
                "is_featured": True,
                "is_active": True,
            },
        )
        delete_response = self.client.post(reverse("delete_event", args=[event.pk]))

        self.assertRedirects(create_response, reverse("manage_events"))
        self.assertRedirects(update_response, reverse("manage_events"))
        self.assertRedirects(delete_response, reverse("manage_events"))
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())
        self.assertGreaterEqual(AuditLog.objects.filter(church=self.church, object_type="Event").count(), 3)

    def test_sermon_member_and_page_crud(self):
        sermon_response = self.client.post(
            reverse("add_sermon"),
            {
                "title": "La gr?ce suffit",
                "preacher": "Pasteur Samuel",
                "description": "Message",
                "sermon_date": "2026-05-01",
                "bible_reference": "2 Corinthiens 12:9",
                "visibility": "public",
                "is_featured": False,
                "is_active": True,
            },
        )
        member_response = self.client.post(
            reverse("add_member"),
            {
                "first_name": "Gr?ce",
                "last_name": "Kabongo",
                "email": "grace@example.com",
                "phone": "+243810000010",
                "directory_consent": True,
                "directory_consent_source": "Formulaire papier",
            },
        )
        page_response = self.client.post(
            reverse("add_page"),
            {
                "title": "Notre vision",
                "content": "<p>Contenu vision</p>",
                "sort_order": 1,
                "is_in_menu": True,
                "visibility": "public",
                "is_active": True,
            },
        )

        self.assertRedirects(sermon_response, reverse("manage_sermons"))
        self.assertRedirects(member_response, reverse("manage_members"))
        self.assertRedirects(page_response, reverse("manage_pages"))
        self.assertTrue(Sermon.objects.filter(church=self.church, title="La gr?ce suffit").exists())
        self.assertTrue(Member.objects.filter(church=self.church, email="grace@example.com").exists())
        saved_page = Page.objects.get(church=self.church, title="Notre vision")
        self.assertEqual(saved_page.content, "Contenu vision")

    def test_church_settings_update_creates_audit_log(self):
        response = self.client.post(
            reverse("church_settings"),
            {
                "name": "Dashboard Church",
                "description": "Nouvelle description",
                "address": "Avenue du Test",
                "city": "Kinshasa",
                "country": "RDC",
                "phone": "+243810000111",
                "email": "contact@example.com",
                "facebook": "",
                "youtube": "",
                "instagram": "",
                "primary_color": "#111111",
                "secondary_color": "#222222",
                "welcome_message": "Bienvenue",
                "service_times": "Dimanche 9h",
                "pastor_name": "Pasteur Test",
            },
        )

        self.assertRedirects(response, reverse("church_settings"))
        self.assertTrue(AuditLog.objects.filter(church=self.church, action="settings_update").exists())

