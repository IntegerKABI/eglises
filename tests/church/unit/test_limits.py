from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Prefetch
from django.utils import timezone
from django.test.utils import CaptureQueriesContext

from church.limits import (
    enforce_count_limit,
    get_plan_usage,
    get_plan_usage_for_churches,
    get_storage_usage_bytes,
    get_resource_count,
    get_retention_cutoff,
)
from church.models import Church, ChurchInvitation, ChurchMembership
from tests.factories import SaaSTestCase


class LimitUnitTests(SaaSTestCase):
    def test_get_resource_count_returns_active_user_count_for_memberships(self):
        church = self.create_church()
        active = self.create_user(username="active-user")
        inactive = self.create_user(username="inactive-user")
        self.add_membership(active, church, is_active=True)
        self.add_membership(inactive, church, is_active=False)

        self.assertEqual(get_resource_count(church, "users"), 1)

    def test_get_plan_usage_includes_new_resources(self):
        church = self.create_church()
        admin = self.create_user(username="plan-admin")
        self.add_membership(admin, church)
        self.create_event(church)
        self.create_sermon(church)
        self.create_page(church)
        self.create_member(church)
        self.create_invitation(church, "pending@example.com")

        usage = get_plan_usage(church)

        self.assertEqual(usage["members"], 1)
        self.assertEqual(usage["events"], 1)
        self.assertEqual(usage["sermons"], 1)
        self.assertEqual(usage["pages"], 1)
        self.assertEqual(usage["users"], 1)
        self.assertEqual(usage["pending_invitations"], 1)
        self.assertIn("storage_mb", usage)

    def test_get_resource_count_prefers_annotated_value(self):
        church = self.create_church()
        church.usage_users_count = 7

        self.assertEqual(get_resource_count(church, "users"), 7)

    def test_get_plan_usage_for_churches_returns_usage_by_church_id(self):
        first = self.create_church(name="Usage A")
        second = self.create_church(name="Usage B")
        self.create_member(first)
        self.create_event(first)
        self.create_sermon(second)

        usage_by_church = get_plan_usage_for_churches([first, second])

        self.assertEqual(usage_by_church[first.pk]["members"], 1)
        self.assertEqual(usage_by_church[first.pk]["events"], 1)
        self.assertEqual(usage_by_church[second.pk]["sermons"], 1)

    def test_get_storage_usage_bytes_uses_prefetched_storage_relations(self):
        church = self.create_church(name="Storage Prefetch")
        self.create_event(church)
        self.create_sermon(church)
        self.create_member(church)
        self.create_page(church)
        ChurchInvitation.objects.create(church=church, email="prefetch@example.com")

        prefetched_church = Church.objects.prefetch_related(
            Prefetch("events", to_attr="_prefetched_storage_events"),
            Prefetch("sermons", to_attr="_prefetched_storage_sermons"),
            Prefetch("members", to_attr="_prefetched_storage_members"),
            Prefetch("pages", to_attr="_prefetched_storage_pages"),
        ).get(pk=church.pk)

        with CaptureQueriesContext(connection) as ctx:
            usage_bytes = get_storage_usage_bytes(prefetched_church)

        self.assertGreaterEqual(usage_bytes, 0)
        self.assertEqual(len(ctx.captured_queries), 0)

    def test_usage_cache_is_invalidated_when_member_changes(self):
        cache.clear()
        church = self.create_church()
        self.assertEqual(get_plan_usage(church)["members"], 0)

        self.create_member(church)

        self.assertEqual(get_plan_usage(church)["members"], 1)

    def test_get_retention_cutoff_respects_override(self):
        church = self.create_church(notification_retention_days_override=15)
        cutoff = get_retention_cutoff(church, "notification_retention_days")

        self.assertIsNotNone(cutoff)
        self.assertLessEqual((timezone.now() - cutoff).days, 15)

    def test_enforce_count_limit_allows_unlimited_plan(self):
        church = self.create_church(plan="scale")

        enforce_count_limit(church, "events", current_count=1000)

    def test_enforce_count_limit_raises_when_limit_reached(self):
        church = self.create_church(max_users_override=1)

        with self.assertRaises(ValidationError):
            enforce_count_limit(church, "users", current_count=1)

