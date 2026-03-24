from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .models import (
    Church,
    ChurchInvitation,
    ChurchMembership,
    ContactMessage,
    Event,
    Member,
    Notification,
    Page,
    Sermon,
)


COUNT_RESOURCE_CONFIG = {
    "members": {
        "model": Member,
        "label": "membres",
        "annotation": "usage_members_count",
        "queryset": lambda church: Member.objects.filter(church=church),
    },
    "events": {
        "model": Event,
        "label": "evenements",
        "annotation": "usage_events_count",
        "queryset": lambda church: Event.objects.filter(church=church),
    },
    "sermons": {
        "model": Sermon,
        "label": "predications",
        "annotation": "usage_sermons_count",
        "queryset": lambda church: Sermon.objects.filter(church=church),
    },
    "pages": {
        "model": Page,
        "label": "pages",
        "annotation": "usage_pages_count",
        "queryset": lambda church: Page.objects.filter(church=church),
    },
    "users": {
        "model": ChurchMembership,
        "label": "utilisateurs",
        "annotation": "usage_users_count",
        "queryset": lambda church: ChurchMembership.objects.filter(church=church, is_active=True),
    },
    "pending_invitations": {
        "model": ChurchInvitation,
        "label": "invitations en attente",
        "annotation": "usage_pending_invitations_count",
        "queryset": lambda church: ChurchInvitation.objects.actionable().filter(church=church),
    },
}

PLAN_USAGE_CACHE_KEY_TEMPLATE = "church:plan-usage:{church_id}:v1"
PLAN_USAGE_CACHE_TIMEOUT = 300

RETENTION_RESOURCE_CONFIG = {
    "message_retention_days": {
        "label": "messages",
    },
    "notification_retention_days": {
        "label": "notifications",
    },
}


def _field_file_size(field_file):
    if not field_file:
        return 0
    try:
        return field_file.size or 0
    except (FileNotFoundError, OSError, ValueError):
        return 0


def _storage_related_items(church, attr_name, model, field_name):
    prefetched_items = getattr(church, attr_name, None)
    if prefetched_items is not None:
        return prefetched_items
    return model.objects.filter(church=church).only(field_name)


def get_storage_usage_bytes(church):
    total = 0
    total += _field_file_size(church.logo)
    total += _field_file_size(church.cover_image)

    for event in _storage_related_items(church, "_prefetched_storage_events", Event, "image"):
        total += _field_file_size(event.image)
    for sermon in _storage_related_items(church, "_prefetched_storage_sermons", Sermon, "image"):
        total += _field_file_size(sermon.image)
    for member in _storage_related_items(church, "_prefetched_storage_members", Member, "photo"):
        total += _field_file_size(member.photo)
    for page in _storage_related_items(church, "_prefetched_storage_pages", Page, "image"):
        total += _field_file_size(page.image)
    return total


def get_storage_usage_mb(church):
    return round(get_storage_usage_bytes(church) / (1024 * 1024), 2)


def get_resource_count(church, resource):
    config = COUNT_RESOURCE_CONFIG[resource]
    annotation_name = config.get("annotation")
    if annotation_name and hasattr(church, annotation_name):
        return getattr(church, annotation_name)
    return config["queryset"](church).count()


def _build_plan_usage(church):
    """Build the tenant usage snapshot from database state."""
    usage = {
        resource: get_resource_count(church, resource)
        for resource in COUNT_RESOURCE_CONFIG
    }
    usage["storage_mb"] = get_storage_usage_mb(church)
    return usage


def get_plan_usage_cache_key(church_id):
    """Return the cache key used for a tenant usage snapshot."""
    return PLAN_USAGE_CACHE_KEY_TEMPLATE.format(church_id=church_id)


def invalidate_plan_usage_cache(church_id):
    """Invalidate the cached plan usage snapshot for a tenant."""
    cache.delete(get_plan_usage_cache_key(church_id))


def get_plan_usage(church, *, use_cache=True):
    """Return the tenant usage snapshot, optionally using the cache."""
    if not use_cache:
        return _build_plan_usage(church)

    cache_key = get_plan_usage_cache_key(church.pk)
    cached_usage = cache.get(cache_key)
    if cached_usage is not None:
        return cached_usage

    usage = _build_plan_usage(church)
    cache.set(cache_key, usage, timeout=PLAN_USAGE_CACHE_TIMEOUT)
    return usage


def get_plan_usage_for_churches(churches):
    """Return usage snapshots for a sequence of churches keyed by church id."""
    church_list = list(churches)
    if not church_list:
        return {}

    cache_keys = {
        get_plan_usage_cache_key(church.pk): church.pk
        for church in church_list
    }
    cached_values = cache.get_many(cache_keys.keys())
    usage_by_church = {
        church_id: cached_values[cache_key]
        for cache_key, church_id in cache_keys.items()
        if cache_key in cached_values
    }

    for church in church_list:
        if church.pk in usage_by_church:
            continue
        usage = _build_plan_usage(church)
        usage_by_church[church.pk] = usage
        cache.set(get_plan_usage_cache_key(church.pk), usage, timeout=PLAN_USAGE_CACHE_TIMEOUT)

    return usage_by_church


def _raise_limit_error(message):
    raise ValidationError(message)


def enforce_count_limit(church, resource, current_count):
    limit = church.get_plan_limit(resource)
    if limit is None:
        return
    if current_count >= limit:
        label = COUNT_RESOURCE_CONFIG.get(resource, {}).get("label", resource)
        _raise_limit_error(
            f"Limite du plan atteinte pour les {label} ({limit}). "
            "Passez a un plan superieur ou ajustez la limite."
        )


def _get_existing_file_size(instance, field_name):
    if not instance or not getattr(instance, "pk", None):
        return 0
    return _field_file_size(getattr(instance, field_name, None))


def get_storage_delta_bytes(form):
    instance = getattr(form, "instance", None)
    total = 0
    for field_name, uploaded_file in form.files.items():
        total += getattr(uploaded_file, "size", 0)
        total -= _get_existing_file_size(instance, field_name)
    return max(total, 0)


def enforce_storage_limit(church, extra_bytes):
    limit_mb = church.get_plan_limit("storage_mb")
    if limit_mb is None or extra_bytes <= 0:
        return
    current_bytes = get_storage_usage_bytes(church)
    limit_bytes = limit_mb * 1024 * 1024
    if current_bytes + extra_bytes > limit_bytes:
        _raise_limit_error(
            f"Limite de stockage du plan atteinte ({limit_mb} Mo). "
            "Supprimez des fichiers, augmentez la limite ou changez de plan."
        )


def get_retention_cutoff(church, resource):
    retention_days = church.get_plan_limit(resource)
    if not retention_days:
        return None
    return timezone.now() - timedelta(days=retention_days)


def filter_messages_for_retention(queryset, church):
    cutoff = get_retention_cutoff(church, "message_retention_days")
    if cutoff is None:
        return queryset
    return queryset.filter(
        Q(created_at__gte=cutoff)
        | Q(status__in=[ContactMessage.Status.NEW, ContactMessage.Status.READ])
    )


def filter_notifications_for_retention(queryset, churches):
    church_list = list(churches)
    if not church_list:
        return queryset.none()

    retention_filter = Q()
    unrestricted_ids = []

    for church in church_list:
        cutoff = get_retention_cutoff(church, "notification_retention_days")
        if cutoff is None:
            unrestricted_ids.append(church.pk)
            continue
        retention_filter |= Q(church=church, created_at__gte=cutoff)

    if unrestricted_ids:
        retention_filter |= Q(church_id__in=unrestricted_ids)

    return queryset.filter(retention_filter) if retention_filter else queryset.none()


def purge_expired_activity(church):
    notification_cutoff = get_retention_cutoff(church, "notification_retention_days")
    deleted_notifications = 0
    if notification_cutoff is not None:
        deleted_notifications, _ = Notification.objects.filter(
            church=church,
            created_at__lt=notification_cutoff,
        ).delete()

    message_cutoff = get_retention_cutoff(church, "message_retention_days")
    deleted_messages = 0
    if message_cutoff is not None:
        deleted_messages, _ = ContactMessage.objects.filter(
            church=church,
            created_at__lt=message_cutoff,
            status__in=[ContactMessage.Status.RESPONDED, ContactMessage.Status.ARCHIVED],
        ).delete()

    return {
        "notifications_deleted": deleted_notifications,
        "messages_deleted": deleted_messages,
    }


def enforce_limits_for_model(church, model, *, instance=None, form=None):
    is_create = instance is None or not getattr(instance, "pk", None)

    for resource, config in COUNT_RESOURCE_CONFIG.items():
        if model is config["model"] and is_create:
            enforce_count_limit(
                church,
                resource,
                config["queryset"](church).count(),
            )
            break

    if form is not None:
        enforce_storage_limit(church, get_storage_delta_bytes(form))
