from django.apps import apps
from django.core.exceptions import ValidationError


SINGLE_CHURCH_MEMBERSHIP_ERROR = (
    "Un utilisateur non super-admin ne peut appartenir qu'a une seule eglise active. "
    "Ce compte est deja actif dans l'eglise {church_name}."
)


def get_active_memberships_for_user(user):
    """Return active memberships for a user."""
    ChurchMembership = apps.get_model("church", "ChurchMembership")
    if user is None or not getattr(user, "pk", None):
        return ChurchMembership.objects.none()
    return ChurchMembership.objects.filter(
        user=user,
        is_active=True,
    ).select_related("church")


def get_conflicting_active_membership(user, *, church=None):
    """Return another active membership that conflicts with the single-church rule."""
    memberships = get_active_memberships_for_user(user)
    church_id = getattr(church, "pk", church)
    if church_id is not None:
        memberships = memberships.exclude(church_id=church_id)
    return memberships.order_by("church__name", "pk").first()


def validate_single_church_membership(user, *, church=None):
    """Raise a validation error when a non-superuser is active in another church."""
    if user is None or getattr(user, "is_superuser", False):
        return
    conflict = get_conflicting_active_membership(user, church=church)
    if conflict is None:
        return
    raise ValidationError(
        SINGLE_CHURCH_MEMBERSHIP_ERROR.format(church_name=conflict.church.name)
    )


def get_pending_invitations_for_user(user):
    """Return active pending invitations that match the authenticated user's email."""
    ChurchInvitation = apps.get_model("church", "ChurchInvitation")
    if (
        user is None
        or not getattr(user, "is_authenticated", False)
        or not getattr(user, "email", "")
    ):
        return ChurchInvitation.objects.none()
    return (
        ChurchInvitation.objects.actionable()
        .filter(email__iexact=user.email.strip())
        .select_related("church", "invited_by")
        .order_by("expires_at", "church__name")
    )
