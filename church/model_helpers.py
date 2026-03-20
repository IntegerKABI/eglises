"""Shared model helpers and plan constants for the church domain."""

import os
from datetime import timedelta
from uuid import uuid4

from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify


def _generate_unique_slug(base_value, queryset, max_length, fallback):
    """Generate a unique slug inside the provided queryset."""
    base_slug = slugify(base_value) or fallback
    if max_length:
        base_slug = base_slug[:max_length]
    slug = base_slug
    counter = 2
    while queryset.filter(slug=slug).exists():
        suffix = f"-{counter}"
        trimmed = base_slug
        if max_length and len(base_slug) + len(suffix) > max_length:
            trimmed = base_slug[: max_length - len(suffix)]
        slug = f"{trimmed}{suffix}"
        counter += 1
    return slug


SITE_SETTINGS_CACHE_KEY = "site_settings:singleton:v1"


def _uuid_filename(filename):
    _, ext = os.path.splitext(filename)
    return f"{uuid4().hex}{ext.lower()}"


def upload_church_logo(instance, filename):
    return f"churches/logos/{_uuid_filename(filename)}"


def upload_church_cover(instance, filename):
    return f"churches/covers/{_uuid_filename(filename)}"


def upload_event_image(instance, filename):
    return f"events/{_uuid_filename(filename)}"


def upload_sermon_image(instance, filename):
    return f"sermons/{_uuid_filename(filename)}"


def upload_member_photo(instance, filename):
    return f"members/{_uuid_filename(filename)}"


def upload_page_image(instance, filename):
    return f"pages/{_uuid_filename(filename)}"


def upload_site_asset(instance, filename):
    return f"site/{_uuid_filename(filename)}"


def _default_invite_expiry():
    return timezone.now() + timedelta(days=7)


def filter_public_queryset(queryset):
    """Limit a queryset to active public records already published."""
    now = timezone.now()
    return queryset.filter(
        visibility='public',
        is_active=True,
    ).filter(
        Q(published_at__isnull=True) | Q(published_at__lte=now)
    )


CHURCH_PLAN_LIMITS = {
    "starter": {
        "members": 200,
        "events": 50,
        "sermons": 100,
        "pages": 12,
        "users": 5,
        "pending_invitations": 10,
        "storage_mb": 512,
        "message_retention_days": 90,
        "notification_retention_days": 30,
    },
    "growth": {
        "members": 1000,
        "events": 300,
        "sermons": 500,
        "pages": 40,
        "users": 20,
        "pending_invitations": 50,
        "storage_mb": 2048,
        "message_retention_days": 180,
        "notification_retention_days": 90,
    },
    "scale": {
        "members": None,
        "events": None,
        "sermons": None,
        "pages": None,
        "users": None,
        "pending_invitations": None,
        "storage_mb": 10240,
        "message_retention_days": 365,
        "notification_retention_days": 180,
    },
}
