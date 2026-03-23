"""Cache-backed request throttling helpers for public and authenticated entry points."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
import time

from django.conf import settings
from django.core.cache import cache


DEFAULT_RATE_LIMITS = {
    "login_ip": {"limit": 10, "window": 900},
    "login_account": {"limit": 5, "window": 900},
    "contact_ip": {"limit": 5, "window": 900},
    "contact_email": {"limit": 3, "window": 900},
    "invite_accept_ip": {"limit": 10, "window": 1800},
    "invite_accept_identity": {"limit": 5, "window": 1800},
    "invite_send_ip": {"limit": 20, "window": 3600},
    "invite_send_actor": {"limit": 10, "window": 3600},
}

RATE_LIMIT_KEY_PREFIX = "rate_limit:v1"


@dataclass(frozen=True)
class RateLimitRule:
    """Describe one throttle bucket that should be consumed for a request."""

    name: str
    identifier: str
    limit: int
    window: int


@dataclass(frozen=True)
class RateLimitResult:
    """Return the outcome of a rate-limit check."""

    limited: bool
    retry_after_seconds: int = 0
    rule_name: str = ""


def get_client_ip(request) -> str:
    """Return the best-effort client IP address for throttling."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    return request.META.get("REMOTE_ADDR", "unknown")


def build_rate_limit_message(retry_after_seconds: int) -> str:
    """Return a user-facing French message for a throttled action."""
    retry_after_seconds = max(1, int(retry_after_seconds))
    if retry_after_seconds < 60:
        return "Trop de tentatives. Reessayez dans quelques secondes."
    retry_after_minutes = math.ceil(retry_after_seconds / 60)
    return f"Trop de tentatives. Reessayez dans {retry_after_minutes} minute(s)."


def build_login_rate_limit_rules(request, username: str) -> list[RateLimitRule]:
    """Build the login throttle buckets for the request."""
    return [
        build_rate_limit_rule("login_ip", get_client_ip(request)),
        build_rate_limit_rule("login_account", _normalize_identifier(username)),
    ]


def build_contact_rate_limit_rules(request, church, sender_email: str) -> list[RateLimitRule]:
    """Build contact form throttle buckets for the request."""
    return [
        build_rate_limit_rule("contact_ip", get_client_ip(request)),
        build_rate_limit_rule(
            "contact_email",
            f"{church.pk}:{_normalize_identifier(sender_email)}",
        ),
    ]


def build_invite_accept_rate_limit_rules(request, invite, identity: str) -> list[RateLimitRule]:
    """Build invitation acceptance throttle buckets for the request."""
    return [
        build_rate_limit_rule("invite_accept_ip", get_client_ip(request)),
        build_rate_limit_rule(
            "invite_accept_identity",
            f"{invite.pk}:{_normalize_identifier(identity)}",
        ),
    ]


def build_invite_send_rate_limit_rules(request, actor, scope_key: str) -> list[RateLimitRule]:
    """Build invitation sending throttle buckets for the request."""
    return [
        build_rate_limit_rule("invite_send_ip", get_client_ip(request)),
        build_rate_limit_rule("invite_send_actor", f"{scope_key}:{actor.pk}"),
    ]


def build_rate_limit_rule(name: str, identifier: str) -> RateLimitRule:
    """Create one throttle rule from the project configuration."""
    config = _get_rate_limit_config(name)
    return RateLimitRule(
        name=name,
        identifier=identifier,
        limit=int(config["limit"]),
        window=int(config["window"]),
    )


def consume_rate_limits(rules: list[RateLimitRule]) -> RateLimitResult:
    """Consume the provided throttle buckets and report whether any limit is exceeded."""
    for rule in rules:
        count = _increment_rule(rule)
        if count > rule.limit:
            return RateLimitResult(
                limited=True,
                retry_after_seconds=_get_retry_after_seconds(rule),
                rule_name=rule.name,
            )
    return RateLimitResult(limited=False)


def reset_rate_limits(rules: list[RateLimitRule]) -> None:
    """Clear throttle buckets after a successful action."""
    for rule in rules:
        cache.delete_many([_counter_cache_key(rule), _expiry_cache_key(rule)])


def _get_rate_limit_config(name: str) -> dict[str, int]:
    configured_limits = getattr(settings, "RATE_LIMITS", {})
    default_config = DEFAULT_RATE_LIMITS[name]
    override_config = configured_limits.get(name, {})
    return {
        "limit": int(override_config.get("limit", default_config["limit"])),
        "window": int(override_config.get("window", default_config["window"])),
    }


def _increment_rule(rule: RateLimitRule) -> int:
    counter_key = _counter_cache_key(rule)
    expiry_key = _expiry_cache_key(rule)
    expires_at = int(time.time()) + rule.window

    if cache.add(counter_key, 1, timeout=rule.window):
        cache.set(expiry_key, expires_at, timeout=rule.window)
        return 1

    try:
        count = cache.incr(counter_key)
    except ValueError:
        cache.set(counter_key, 1, timeout=rule.window)
        cache.set(expiry_key, expires_at, timeout=rule.window)
        return 1

    if cache.get(expiry_key) is None:
        cache.set(expiry_key, expires_at, timeout=rule.window)
    return count


def _get_retry_after_seconds(rule: RateLimitRule) -> int:
    expiry_value = cache.get(_expiry_cache_key(rule))
    if not expiry_value:
        return rule.window
    return max(1, int(expiry_value - time.time()))


def _counter_cache_key(rule: RateLimitRule) -> str:
    return f"{RATE_LIMIT_KEY_PREFIX}:{rule.name}:{_hash_identifier(rule.identifier)}"


def _expiry_cache_key(rule: RateLimitRule) -> str:
    return f"{_counter_cache_key(rule)}:expires"


def _hash_identifier(identifier: str) -> str:
    return sha256(identifier.encode("utf-8")).hexdigest()


def _normalize_identifier(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized or "anonymous"
