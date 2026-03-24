import importlib.util
import os
import unittest
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from church.models import Church, ChurchInvitation, ChurchMembership, ContactMessage, Event, Notification, Page, Sermon
from tests.factories import TEST_STORAGES


playwright_available = importlib.util.find_spec("playwright") is not None


@override_settings(
    STORAGES=TEST_STORAGES,
    ALLOWED_HOSTS=["localhost", "127.0.0.1", "testserver"],
)
class BrowserJourneyTests(StaticLiveServerTestCase):
    """Browser-driven journeys for the highest-value church SaaS flows."""

    databases = {"default"}
    password = "StrongPass123!"

    @classmethod
    def setUpClass(cls):
        if not playwright_available:
            raise unittest.SkipTest("Playwright is not installed in the test environment.")
        if os.name == "nt" and os.environ.get("ENABLE_WINDOWS_PLAYWRIGHT_E2E") != "1":
            raise unittest.SkipTest(
                "Browser E2E tests are disabled on Windows unless ENABLE_WINDOWS_PLAYWRIGHT_E2E=1 is set."
            )

        super().setUpClass()
        from playwright.sync_api import Error, sync_playwright

        try:
            cls._playwright = sync_playwright().start()
            cls.browser = cls._playwright.chromium.launch(headless=True)
        except (Error, OSError, PermissionError) as exc:
            if hasattr(cls, "_playwright"):
                cls._playwright.stop()
            super().tearDownClass()
            raise unittest.SkipTest(
                "Playwright is installed, but the browser process could not start in this environment."
            ) from exc

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
        if hasattr(cls, "_playwright"):
            cls._playwright.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        user_model = get_user_model()
        self.superadmin = user_model.objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password=self.password,
        )
        self.admin_user = user_model.objects.create_user(
            username="tenantadmin",
            email="tenantadmin@example.com",
            password=self.password,
            first_name="Andre",
            last_name="Kasongo",
        )
        self.invited_user = user_model.objects.create_user(
            username="inviteduser",
            email="invited@example.com",
            password=self.password,
        )
        self.declining_user = user_model.objects.create_user(
            username="declineuser",
            email="decline@example.com",
            password=self.password,
        )
        self.secretary_user = user_model.objects.create_user(
            username="secretary",
            email="secretary@example.com",
            password=self.password,
        )

        self.primary_church = Church.objects.create(
            name="Communaute de la Grace",
            city="Kinshasa",
            status=Church.Status.ACTIVE,
        )
        self.secondary_church = Church.objects.create(
            name="Assemblee de l'Espoir",
            city="Lubumbashi",
            status=Church.Status.ACTIVE,
        )

        ChurchMembership.objects.create(
            user=self.admin_user,
            church=self.primary_church,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )
        ChurchMembership.objects.create(
            user=self.secretary_user,
            church=self.primary_church,
            role=ChurchMembership.Role.SECRETARY,
            is_active=True,
        )

        Event.objects.create(
            church=self.primary_church,
            title="Veille de priere",
            event_date=date.today() + timedelta(days=3),
            location="Temple central",
            visibility="public",
            is_active=True,
        )
        for index in range(12):
            Event.objects.create(
                church=self.primary_church,
                title=f"Evenement public {index + 1}",
                event_date=date.today() + timedelta(days=index + 1),
                visibility="public",
                is_active=True,
            )
        Sermon.objects.create(
            church=self.primary_church,
            title="La foi qui persiste",
            preacher="Pasteur Andre",
            sermon_date=date.today(),
            visibility="public",
            is_active=True,
        )
        self.public_page = Page.objects.create(
            church=self.primary_church,
            title="A propos",
            content="Bienvenue dans notre communaute.",
            visibility="public",
            is_active=True,
            is_in_menu=True,
        )
        self.contact_message = ContactMessage.objects.create(
            church=self.primary_church,
            sender_name="Visiteur",
            sender_email="visitor@example.com",
            subject="Demande de priere",
            message="Merci de prier pour ma famille.",
            status=ContactMessage.Status.NEW,
        )
        self.notification = Notification.objects.create(
            church=self.primary_church,
            recipient=self.admin_user,
            category=Notification.Category.EVENT,
            title="Nouvel evenement",
            body="Un evenement a ete programme.",
            link=reverse("manage_events"),
            is_read=False,
        )
        self.accept_invitation = ChurchInvitation.objects.create(
            church=self.primary_church,
            email=self.invited_user.email,
            role=ChurchMembership.Role.STAFF,
            invited_by=self.admin_user,
        )
        self.decline_invitation = ChurchInvitation.objects.create(
            church=self.primary_church,
            email=self.declining_user.email,
            role=ChurchMembership.Role.STAFF,
            invited_by=self.admin_user,
        )

    def new_page(self):
        page = self.browser.new_page()
        page.set_default_timeout(7000)
        return page

    def login(self, page, username, password):
        page.goto(f"{self.live_server_url}/login/")
        page.locator('input[name="username"]').fill(username)
        page.locator('input[name="password"]').fill(password)
        page.locator('button[type="submit"]').click()
        page.wait_for_load_state("networkidle")

    def test_public_pages_render_with_pagination_in_browser(self):
        page = self.new_page()
        try:
            page.goto(f"{self.live_server_url}/")
            self.assertIn("Communaute de la Grace", page.content())

            page.goto(f"{self.live_server_url}/eglise/{self.primary_church.slug}/")
            self.assertIn("Communaute de la Grace", page.content())

            page.goto(f"{self.live_server_url}/eglise/{self.primary_church.slug}/evenements/?page=2")
            self.assertIn("Evenement public 1", page.content())

            page.goto(f"{self.live_server_url}/eglise/{self.primary_church.slug}/predications/")
            self.assertIn("La foi qui persiste", page.content())

            page.goto(
                f"{self.live_server_url}/eglise/{self.primary_church.slug}/page/{self.public_page.slug}/"
            )
            self.assertIn("Bienvenue dans notre communaute.", page.content())
        finally:
            page.close()

    def test_admin_can_log_in_and_create_an_event(self):
        page = self.new_page()
        try:
            self.login(page, self.admin_user.username, self.password)
            page.wait_for_load_state("networkidle")
            self.assertIn(self.primary_church.name, page.content())

            page.goto(f"{self.live_server_url}/dashboard/evenements/ajouter/")
            page.locator('input[name="title"]').fill("Conference jeunesse")
            page.locator('input[name="event_date"]').fill(str(date.today() + timedelta(days=30)))
            page.locator('input[name="location"]').fill("Salle polyvalente")
            page.locator('button[type="submit"]').click()
            page.wait_for_url("**/dashboard/evenements/")

            self.assertTrue(
                Event.objects.filter(church=self.primary_church, title="Conference jeunesse").exists()
            )
            self.assertIn("Conference jeunesse", page.content())
        finally:
            page.close()

    def test_invited_user_can_accept_an_invitation_from_the_pending_inbox(self):
        page = self.new_page()
        try:
            self.login(page, self.invited_user.username, self.password)
            page.wait_for_url("**/invitations/")
            page.locator(f'a[href="/invite/{self.accept_invitation.token}/"]').click()
            page.wait_for_url(f"**/invite/{self.accept_invitation.token}/")
            page.locator('button[type="submit"]').click()
            page.wait_for_load_state("networkidle")

            self.accept_invitation.refresh_from_db()
            self.assertEqual(self.accept_invitation.status, ChurchInvitation.Status.ACCEPTED)
            self.assertTrue(
                ChurchMembership.objects.filter(
                    user=self.invited_user,
                    church=self.primary_church,
                    is_active=True,
                ).exists()
            )
        finally:
            page.close()

    def test_invited_user_can_decline_and_is_redirected_home(self):
        page = self.new_page()
        try:
            self.login(page, self.declining_user.username, self.password)
            page.wait_for_url("**/invitations/")
            page.locator(
                f'form[action="/invite/{self.decline_invitation.token}/decline/"] button[type="submit"]'
            ).click()
            page.wait_for_url("**/")

            self.decline_invitation.refresh_from_db()
            self.assertEqual(self.decline_invitation.status, ChurchInvitation.Status.DECLINED)
            self.assertIn("Invitation refusee", page.content())
        finally:
            page.close()

    def test_superadmin_can_switch_church_context_from_support_console(self):
        page = self.new_page()
        try:
            self.login(page, self.superadmin.username, self.password)
            page.wait_for_load_state("networkidle")
            page.goto(f"{self.live_server_url}/dashboard/platform/churches/{self.secondary_church.pk}/")
            page.locator('form[action$="/switch/"] button[type="submit"]').click()
            page.wait_for_load_state("networkidle")
            self.assertIn(self.secondary_church.name, page.content())
        finally:
            page.close()

    def test_opening_notifications_and_messages_marks_them_as_read(self):
        page = self.new_page()
        try:
            self.login(page, self.admin_user.username, self.password)
            page.wait_for_load_state("networkidle")

            page.goto(f"{self.live_server_url}/dashboard/notifications/")
            page.locator(f'a[href="/dashboard/notifications/{self.notification.pk}/open/"]').click()
            page.wait_for_url("**/dashboard/evenements/")
            self.notification.refresh_from_db()
            self.assertTrue(self.notification.is_read)

            page.goto(f"{self.live_server_url}/dashboard/messages/")
            page.locator(f'a[href="/dashboard/messages/{self.contact_message.pk}/"]').click()
            page.wait_for_url(f"**/dashboard/messages/{self.contact_message.pk}/")
            self.contact_message.refresh_from_db()
            self.assertEqual(self.contact_message.status, ContactMessage.Status.READ)
        finally:
            page.close()
