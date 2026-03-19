from django.test import RequestFactory

from church.context_processors import church_context
from church.models import ChurchMembership, SiteSettings
from tests.factories import SaaSTestCase


class ContextProcessorTests(SaaSTestCase):
    def test_church_context_exposes_expected_values(self):
        user = self.create_user(username="context-user", email="context-user@example.com")
        church = self.create_church(name="Context Church")
        membership = self.add_membership(user, church, role=ChurchMembership.Role.ADMIN)
        page = self.create_page(church, title="Page menu")

        request = RequestFactory().get("/")
        request.user = user
        request.session = self.client.session
        request.current_church = church
        request.current_membership = membership
        request.current_church.menu_pages = [page]

        context = church_context(request)

        self.assertEqual(context["current_church"], church)
        self.assertEqual(context["current_membership"], membership)
        self.assertEqual(context["membership_role"], ChurchMembership.Role.ADMIN)
        self.assertEqual(context["menu_pages"], [page])
        self.assertIn("site_settings", context)
        self.assertTrue(context["can_view_audit"])

    def test_church_context_uses_site_settings_singleton(self):
        site = SiteSettings.get()
        request = RequestFactory().get("/")
        request.user = self.create_user(username="site-user")
        request.session = self.client.session
        request.current_church = None
        request.current_membership = None

        context = church_context(request)

        self.assertEqual(context["site_settings"].pk, site.pk)

