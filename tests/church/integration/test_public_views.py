from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from church.models import ChurchMembership, ContactMessage, Notification
from tests.factories import SaaSTestCase


class PublicViewIntegrationTests(SaaSTestCase):
    def test_home_lists_only_active_churches_and_supports_search(self):
        active = self.create_church(name="Source de Vie", city="Kinshasa")
        self.create_church(name="B?thanie", city="Lubumbashi", status="draft")

        response = self.client.get(reverse("home"), {"q": "Kinshasa"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, active.name)
        self.assertNotContains(response, "B?thanie")

    def test_home_paginates_results(self):
        for index in range(10):
            self.create_church(name=f"Church {index}")

        response = self.client.get(reverse("home"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_previous())

    def test_church_home_only_shows_public_published_content(self):
        church = self.create_church(name="Accueil Church")
        self.create_event(
            church,
            title="Visible",
            event_date=timezone.now().date() + timedelta(days=1),
            published_at=timezone.now() - timedelta(hours=1),
        )
        self.create_event(
            church,
            title="Priv?",
            visibility="private",
            event_date=timezone.now().date() + timedelta(days=1),
        )
        self.create_sermon(church, title="Pr?dication visible", published_at=timezone.now())
        self.create_sermon(church, title="Pr?dication brouillon", visibility="draft")
        self.create_page(church, title="? propos", published_at=timezone.now())
        self.create_page(church, title="Interne", visibility="private")

        response = self.client.get(reverse("church_home", args=[church.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible")
        self.assertContains(response, "Pr?dication visible")
        self.assertContains(response, "? propos")
        self.assertNotContains(response, "Priv?")
        self.assertNotContains(response, "Pr?dication brouillon")
        self.assertNotContains(response, "Interne")

    def test_public_event_list_supports_filters_and_invalid_values_are_safe(self):
        church = self.create_church(name="Events Church")
        upcoming = self.create_event(
            church,
            title="Conf?rence jeunesse",
            is_featured=True,
            event_date=timezone.now().date() + timedelta(days=1),
        )
        self.create_event(
            church,
            title="Ancien ?v?nement",
            event_date=timezone.now().date() - timedelta(days=1),
            is_featured=False,
        )

        response = self.client.get(
            reverse("church_events", args=[church.slug]),
            {"featured": "true", "when": "upcoming", "q": "jeunesse"},
        )
        invalid_response = self.client.get(
            reverse("church_events", args=[church.slug]),
            {"featured": "maybe", "when": "invalid"},
        )

        self.assertContains(response, upcoming.title)
        self.assertNotContains(response, "Ancien ?v?nement")
        self.assertEqual(invalid_response.status_code, 200)

    def test_public_sermon_list_supports_search_and_featured_filter(self):
        church = self.create_church(name="Sermons Church")
        visible = self.create_sermon(church, title="Esp?rance", preacher="Pasteur David", is_featured=True)
        self.create_sermon(church, title="Foi", preacher="Pasteur Esther", is_featured=False)

        response = self.client.get(
            reverse("church_sermons", args=[church.slug]),
            {"featured": "true", "q": "David"},
        )

        self.assertContains(response, visible.title)
        self.assertNotContains(response, "Foi")

    def test_public_page_requires_public_visibility(self):
        church = self.create_church(name="Pages Church")
        private_page = self.create_page(church, title="Interne", visibility="private")

        response = self.client.get(reverse("church_page", args=[church.slug, private_page.slug]))

        self.assertEqual(response.status_code, 404)

    def test_public_contact_submission_creates_message_and_notifications(self):
        church = self.create_church(name="Contact Church")
        secretary = self.create_user(username="secretary-contact")
        self.add_membership(secretary, church, role=ChurchMembership.Role.SECRETARY)

        response = self.client.post(
            reverse("church_contact", args=[church.slug]),
            {
                "sender_name": "Visiteur",
                "sender_email": "visiteur@example.com",
                "subject": "Demande de pri?re",
                "message": "Merci de prier pour ma famille.",
            },
        )

        self.assertRedirects(response, reverse("church_contact", args=[church.slug]))
        self.assertTrue(ContactMessage.objects.filter(church=church, sender_email="visiteur@example.com").exists())
        self.assertEqual(Notification.objects.filter(church=church, recipient=secretary).count(), 1)

