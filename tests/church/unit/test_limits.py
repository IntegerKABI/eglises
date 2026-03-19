from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from church.limits import (
    enforce_count_limit,
    get_plan_usage,
    get_resource_count,
    get_retention_cutoff,
)
from church.models import ChurchMembership
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

