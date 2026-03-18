from django.core.exceptions import ValidationError

from .models import Church, Event, Member, Page, Sermon


def _field_file_size(field_file):
    if not field_file:
        return 0
    try:
        return field_file.size or 0
    except (FileNotFoundError, OSError, ValueError):
        return 0


def get_storage_usage_bytes(church):
    total = 0
    total += _field_file_size(church.logo)
    total += _field_file_size(church.cover_image)

    for event in Event.objects.filter(church=church).only("image"):
        total += _field_file_size(event.image)
    for sermon in Sermon.objects.filter(church=church).only("image"):
        total += _field_file_size(sermon.image)
    for member in Member.objects.filter(church=church).only("photo"):
        total += _field_file_size(member.photo)
    for page in Page.objects.filter(church=church).only("image"):
        total += _field_file_size(page.image)
    return total


def get_storage_usage_mb(church):
    return round(get_storage_usage_bytes(church) / (1024 * 1024), 2)


def get_plan_usage(church):
    return {
        "members": Member.objects.filter(church=church).count(),
        "events": Event.objects.filter(church=church).count(),
        "storage_mb": get_storage_usage_mb(church),
    }


def _raise_limit_error(message):
    raise ValidationError(message)


def enforce_count_limit(church, resource, current_count):
    limit = church.get_plan_limit(resource)
    if limit is None:
        return
    if current_count >= limit:
        resource_labels = {
            "members": "membres",
            "events": "evenements",
        }
        label = resource_labels.get(resource, resource)
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


def enforce_limits_for_model(church, model, *, instance=None, form=None):
    is_create = instance is None or not getattr(instance, "pk", None)

    if model is Member and is_create:
        enforce_count_limit(church, "members", Member.objects.filter(church=church).count())

    if model is Event and is_create:
        enforce_count_limit(church, "events", Event.objects.filter(church=church).count())

    if form is not None:
        enforce_storage_limit(church, get_storage_delta_bytes(form))
