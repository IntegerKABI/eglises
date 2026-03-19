import importlib.util
import unittest

from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from tests.factories import TEST_STORAGES


playwright_available = importlib.util.find_spec("playwright") is not None


@unittest.skipUnless(playwright_available, "Playwright n'est pas install? dans l'environnement de test.")
class BrowserJourneyTests(StaticLiveServerTestCase):
    """Sc?narios navigateur ? activer quand Playwright sera install?."""

    databases = {"default"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from playwright.sync_api import sync_playwright

        cls._playwright = sync_playwright().start()
        cls.browser = cls._playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._playwright.stop()
        super().tearDownClass()

    def test_home_page_renders_in_browser(self):
        page = self.browser.new_page()
        page.goto(self.live_server_url)
        self.assertIn("?glise", page.title())
        page.close()

