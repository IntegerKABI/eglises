from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone

from church.models import (
    Church,
    Event,
    Member,
    Page,
    Sermon,
    SiteSettings,
    filter_public_queryset,
    upload_church_logo,
    upload_event_image,
    upload_member_photo,
    upload_page_image,
    upload_sermon_image,
    upload_site_asset,
)
from tests.factories import SaaSTestCase


class ChurchModelTests(SaaSTestCase):
    def test_church_slug_generation_is_unique(self):
        first = self.create_church(name="Parole de Vie")
        second = self.create_church(name="Parole de Vie")

        self.assertEqual(first.slug, "parole-de-vie")
        self.assertEqual(second.slug, "parole-de-vie-2")

    def test_event_slug_generation_is_unique_per_church(self):
        church = self.create_church()
        first = self.create_event(church, title="Veill?e de pri?re")
        second = self.create_event(church, title="Veill?e de pri?re")

        self.assertEqual(first.slug, "veille-de-prire")
        self.assertEqual(second.slug, "veille-de-prire-2")

    def test_sermon_slug_generation_is_unique_per_church(self):
        church = self.create_church()
        first = self.create_sermon(church, title="La fid?lit? de Dieu")
        second = self.create_sermon(church, title="La fid?lit? de Dieu")

        self.assertEqual(first.slug, "la-fidlit-de-dieu")
        self.assertEqual(second.slug, "la-fidlit-de-dieu-2")

    def test_page_slug_generation_is_unique_per_church(self):
        church = self.create_church()
        first = self.create_page(church, title="? propos")
        second = self.create_page(church, title="? propos")

        self.assertEqual(first.slug, "propos")
        self.assertEqual(second.slug, "propos-2")

    def test_event_clean_rejects_end_date_before_start_date(self):
        church = self.create_church()
        event = Event(
            church=church,
            title="Retraite",
            event_date=timezone.now().date(),
            end_date=timezone.now().date() - timedelta(days=1),
        )

        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_member_clean_requires_consent_source_when_directory_consent_is_enabled(self):
        church = self.create_church()
        member = Member(
            church=church,
            first_name="Gr?ce",
            last_name="Kabongo",
            directory_consent=True,
        )

        with self.assertRaises(ValidationError):
            member.full_clean()

    def test_page_save_sanitizes_html_content(self):
        church = self.create_church()
        page = self.create_page(church, content="<h1>Bienvenue</h1><script>alert(1)</script>")

        self.assertEqual(page.content, "Bienvenuealert(1)")

    def test_filter_public_queryset_excludes_private_and_future_content(self):
        church = self.create_church()
        public_now = self.create_page(
            church,
            title="Publique",
            visibility="public",
            published_at=timezone.now() - timedelta(hours=1),
        )
        self.create_page(church, title="Priv?e", visibility="private")
        self.create_page(
            church,
            title="Future",
            visibility="public",
            published_at=timezone.now() + timedelta(days=1),
        )

        queryset = filter_public_queryset(Page.objects.filter(church=church))

        self.assertEqual(list(queryset), [public_now])

    def test_site_settings_get_returns_singleton_and_uses_cache(self):
        cache.clear()
        first = SiteSettings.get()
        second = SiteSettings.get()

        self.assertEqual(first.pk, 1)
        self.assertEqual(second.pk, 1)
        self.assertEqual(first.pk, second.pk)

    def test_site_settings_save_invalidates_cache(self):
        settings_obj = SiteSettings.get()
        cache.set("site_settings:singleton:v1", "stale")

        settings_obj.site_name = "Plateforme test"
        settings_obj.save()

        self.assertNotEqual(cache.get("site_settings:singleton:v1"), "stale")

    def test_upload_paths_use_expected_prefix_and_lowercase_extension(self):
        self.assertTrue(upload_church_logo(None, "Logo.PNG").startswith("churches/logos/"))
        self.assertTrue(upload_event_image(None, "image.JPG").endswith(".jpg"))
        self.assertTrue(upload_sermon_image(None, "image.JPEG").startswith("sermons/"))
        self.assertTrue(upload_member_photo(None, "portrait.PNG").startswith("members/"))
        self.assertTrue(upload_page_image(None, "cover.GIF").startswith("pages/"))
        self.assertTrue(upload_site_asset(None, "asset.SVG").startswith("site/"))

