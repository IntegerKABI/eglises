from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from church.models import BackgroundJob, ChurchMembership, ContactMessage, Notification
from tests.factories import SaaSTestCase


class PublicViewIntegrationTests(SaaSTestCase):
    def test_home_lists_only_active_churches_and_supports_search(self):
        active = self.create_church(name="Source de Vie", city="Kinshasa")
        self.create_church(name="Bethanie", city="Lubumbashi", status="draft")

        response = self.client.get(reverse("home"), {"q": "Kinshasa"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, active.name)
        self.assertNotContains(response, "Bethanie")

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
            title="Prive",
            visibility="private",
            event_date=timezone.now().date() + timedelta(days=1),
        )
        self.create_sermon(church, title="Predication visible", published_at=timezone.now())
        self.create_sermon(church, title="Predication brouillon", visibility="draft")
        self.create_page(church, title="A propos", published_at=timezone.now())
        self.create_page(church, title="Interne", visibility="private")

        response = self.client.get(reverse("church_home", args=[church.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible")
        self.assertContains(response, "Predication visible")
        self.assertContains(response, "A propos")
        self.assertNotContains(response, "Prive")
        self.assertNotContains(response, "Predication brouillon")
        self.assertNotContains(response, "Interne")

    def test_public_event_list_supports_filters_and_invalid_values_are_safe(self):
        church = self.create_church(name="Events Church")
        upcoming = self.create_event(
            church,
            title="Conference jeunesse",
            is_featured=True,
            event_date=timezone.now().date() + timedelta(days=1),
        )
        self.create_event(
            church,
            title="Ancien evenement",
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
        self.assertNotContains(response, "Ancien evenement")
        self.assertEqual(invalid_response.status_code, 200)

    def test_public_sermon_list_supports_search_and_featured_filter(self):
        church = self.create_church(name="Sermons Church")
        visible = self.create_sermon(church, title="Esperance", preacher="Pasteur David", is_featured=True)
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

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="tests@example.com",
        BACKGROUND_JOBS_EAGER=False,
    )
    def test_public_contact_submission_notifies_secretary_only_by_default(self):
        church = self.create_church(name="Contact Church")
        admin = self.create_user(username="contact-admin")
        staff = self.create_user(username="contact-staff")
        secretary = self.create_user(username="secretary-contact")
        self.add_membership(admin, church, role=ChurchMembership.Role.ADMIN)
        self.add_membership(staff, church, role=ChurchMembership.Role.STAFF)
        self.add_membership(secretary, church, role=ChurchMembership.Role.SECRETARY)

        response = self.client.post(
            reverse("church_contact", args=[church.slug]),
            {
                "sender_name": "Visiteur",
                "sender_email": "visiteur@example.com",
                "subject": "Demande de priere",
                "message": "Merci de prier pour ma famille.",
            },
        )

        self.assertRedirects(response, reverse("church_contact", args=[church.slug]))
        self.assertTrue(ContactMessage.objects.filter(church=church, sender_email="visiteur@example.com").exists())
        recipients = set(Notification.objects.filter(church=church).values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {secretary.pk})
        self.assertEqual(BackgroundJob.objects.count(), 1)

        call_command("process_background_jobs", stdout=StringIO())

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [secretary.email])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="tests@example.com",
        BACKGROUND_JOBS_EAGER=False,
    )
    def test_public_contact_submission_falls_back_to_admins_without_secretary(self):
        church = self.create_church(name="Fallback Contact Church")
        admin = self.create_user(username="fallback-admin")
        staff = self.create_user(username="fallback-staff")
        self.add_membership(admin, church, role=ChurchMembership.Role.ADMIN)
        self.add_membership(staff, church, role=ChurchMembership.Role.STAFF)

        response = self.client.post(
            reverse("church_contact", args=[church.slug]),
            {
                "sender_name": "Visiteur",
                "sender_email": "visiteur@example.com",
                "subject": "Demande de priere",
                "message": "Merci de prier pour ma famille.",
            },
        )

        self.assertRedirects(response, reverse("church_contact", args=[church.slug]))
        self.assertTrue(ContactMessage.objects.filter(church=church, sender_email="visiteur@example.com").exists())
        recipients = set(Notification.objects.filter(church=church).values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {admin.pk})
        self.assertEqual(BackgroundJob.objects.count(), 1)

        call_command("process_background_jobs", stdout=StringIO())

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [admin.email])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="tests@example.com",
        BACKGROUND_JOBS_EAGER=False,
    )
    def test_public_contact_submission_escalates_to_admin_for_urgent_messages(self):
        church = self.create_church(name="Urgent Contact Church")
        admin = self.create_user(username="urgent-admin")
        secretary = self.create_user(username="urgent-secretary")
        self.add_membership(admin, church, role=ChurchMembership.Role.ADMIN)
        self.add_membership(secretary, church, role=ChurchMembership.Role.SECRETARY)

        response = self.client.post(
            reverse("church_contact", args=[church.slug]),
            {
                "sender_name": "Visiteur",
                "sender_email": "urgent@example.com",
                "subject": "Urgent",
                "message": "Nous avons une urgence familiale.",
            },
        )

        self.assertRedirects(response, reverse("church_contact", args=[church.slug]))
        self.assertTrue(ContactMessage.objects.filter(church=church, sender_email="urgent@example.com").exists())
        recipients = set(Notification.objects.filter(church=church).values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {admin.pk, secretary.pk})
        self.assertEqual(BackgroundJob.objects.filter(job_type=BackgroundJob.JobType.SEND_CONTACT_EMAIL).count(), 2)

        call_command("process_background_jobs", stdout=StringIO())

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [secretary.email])

        delayed_job = BackgroundJob.objects.get(
            job_type=BackgroundJob.JobType.SEND_CONTACT_EMAIL,
            status=BackgroundJob.Status.PENDING,
        )
        self.assertGreater(delayed_job.available_at, timezone.now())
        delayed_job.available_at = timezone.now() - timedelta(seconds=1)
        delayed_job.save(update_fields=["available_at"])

        call_command("process_background_jobs", stdout=StringIO())

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual({message.to[0] for message in mail.outbox}, {admin.email, secretary.email})

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="tests@example.com",
        BACKGROUND_JOBS_EAGER=False,
    )
    def test_public_contact_submission_returns_json_for_ajax(self):
        church = self.create_church(name="Ajax Contact Church")
        secretary = self.create_user(username="ajax-secretary")
        self.add_membership(secretary, church, role=ChurchMembership.Role.SECRETARY)

        response = self.client.post(
            reverse("church_contact", args=[church.slug]),
            {
                "sender_name": "Visiteur AJAX",
                "sender_email": "ajax@example.com",
                "subject": "Besoin d'information",
                "message": "Merci de me recontacter.",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)
        self.assertTrue(ContactMessage.objects.filter(church=church, sender_email="ajax@example.com").exists())
        recipients = set(Notification.objects.filter(church=church).values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {secretary.pk})

    @override_settings(
        RATE_LIMITS={
            "contact_ip": {"limit": 1, "window": 60},
            "contact_email": {"limit": 1, "window": 60},
        }
    )
    def test_public_contact_submission_is_rate_limited(self):
        church = self.create_church(name="Limited Contact Church")
        self.client.defaults["REMOTE_ADDR"] = "10.0.0.11"

        first_response = self.client.post(
            reverse("church_contact", args=[church.slug]),
            {
                "sender_name": "Premier visiteur",
                "sender_email": "limited@example.com",
                "subject": "Question",
                "message": "Premier message.",
            },
        )
        second_response = self.client.post(
            reverse("church_contact", args=[church.slug]),
            {
                "sender_name": "Deuxieme visiteur",
                "sender_email": "limited@example.com",
                "subject": "Question",
                "message": "Deuxieme message.",
            },
            follow=True,
        )

        self.assertRedirects(first_response, reverse("church_contact", args=[church.slug]))
        self.assertEqual(ContactMessage.objects.filter(church=church).count(), 1)
        self.assertContains(second_response, "Trop de tentatives")
        self.assertEqual(ContactMessage.objects.filter(church=church).count(), 1)




