from django.core.cache import cache
from django.test import override_settings

from church.rate_limits import (
    build_rate_limit_message,
    build_rate_limit_rule,
    consume_rate_limits,
    reset_rate_limits,
)
from tests.factories import SaaSTestCase


class RateLimitHelperTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    @override_settings(RATE_LIMITS={"login_ip": {"limit": 1, "window": 60}})
    def test_consume_rate_limits_blocks_after_limit(self):
        rule = build_rate_limit_rule("login_ip", "127.0.0.1")

        first_result = consume_rate_limits([rule])
        second_result = consume_rate_limits([rule])

        self.assertFalse(first_result.limited)
        self.assertTrue(second_result.limited)
        self.assertGreaterEqual(second_result.retry_after_seconds, 1)

    @override_settings(RATE_LIMITS={"login_ip": {"limit": 1, "window": 60}})
    def test_reset_rate_limits_clears_buckets(self):
        rule = build_rate_limit_rule("login_ip", "127.0.0.1")
        consume_rate_limits([rule])
        reset_rate_limits([rule])

        result = consume_rate_limits([rule])

        self.assertFalse(result.limited)

    def test_build_rate_limit_message_formats_minutes(self):
        self.assertEqual(
            build_rate_limit_message(90),
            "Trop de tentatives. Reessayez dans 2 minute(s).",
        )
