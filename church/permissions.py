from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from .membership_policy import get_pending_invitations_for_user
from .models import Church, ChurchMembership
from .tenancy import get_accessible_churches, get_membership, get_selected_church


CAP_VIEW_DASHBOARD = "view_dashboard"
CAP_MANAGE_CHURCH_SETTINGS = "manage_church_settings"
CAP_MANAGE_EVENTS = "manage_events"
CAP_MANAGE_SERMONS = "manage_sermons"
CAP_MANAGE_PAGES = "manage_pages"
CAP_MANAGE_MEMBERS = "manage_members"
CAP_MANAGE_MESSAGES = "manage_messages"
CAP_MANAGE_USERS = "manage_users"
CAP_MANAGE_SITE_SETTINGS = "manage_site_settings"
CAP_VIEW_AUDIT = "view_audit"
CAP_SWITCH_CHURCH = "switch_church"

ALL_CAPABILITIES = {
    CAP_VIEW_DASHBOARD,
    CAP_MANAGE_CHURCH_SETTINGS,
    CAP_MANAGE_EVENTS,
    CAP_MANAGE_SERMONS,
    CAP_MANAGE_PAGES,
    CAP_MANAGE_MEMBERS,
    CAP_MANAGE_MESSAGES,
    CAP_MANAGE_USERS,
    CAP_MANAGE_SITE_SETTINGS,
    CAP_VIEW_AUDIT,
}

# Tenant role policy:
# - admin: full church administration except platform settings
# - staff: content and member operations inside the tenant
# - secretary: office workflow (messages, members, events, sermons)
ROLE_CAPABILITIES = {
    ChurchMembership.Role.ADMIN: ALL_CAPABILITIES - {CAP_MANAGE_SITE_SETTINGS},
    ChurchMembership.Role.STAFF: {
        CAP_VIEW_DASHBOARD,
        CAP_MANAGE_EVENTS,
        CAP_MANAGE_SERMONS,
        CAP_MANAGE_PAGES,
        CAP_MANAGE_MEMBERS,
    },
    ChurchMembership.Role.SECRETARY: {
        CAP_VIEW_DASHBOARD,
        CAP_MANAGE_EVENTS,
        CAP_MANAGE_SERMONS,
        CAP_MANAGE_MESSAGES,
        CAP_MANAGE_MEMBERS,
    },
}


def get_capabilities_for_user(user, membership):
    if user.is_superuser:
        return set(ALL_CAPABILITIES)
    if not membership:
        return set()
    return set(ROLE_CAPABILITIES.get(membership.role, set()))


def get_capabilities_for_request(request):
    church = getattr(request, "current_church", None)
    if church is None and request.user.is_authenticated:
        church = get_selected_church(request, prefetch_pages=True)
        request.current_church = church

    membership = getattr(request, "current_membership", None)
    if membership is None and request.user.is_authenticated and church:
        membership = get_membership(request.user, church)
        request.current_membership = membership

    return get_capabilities_for_user(request.user, membership)


def _roles_for_capability(capability):
    return [
        role
        for role, capabilities in ROLE_CAPABILITIES.items()
        if capability in capabilities
    ]


def get_churches_for_capability(user, capability):
    if not user.is_authenticated:
        return Church.objects.none()
    if user.is_superuser:
        return Church.objects.all().order_by("name", "id")

    roles = _roles_for_capability(capability)
    if not roles:
        return Church.objects.none()

    return (
        Church.objects.filter(
            memberships__user=user,
            memberships__is_active=True,
            memberships__role__in=roles,
            status__in=[Church.Status.ACTIVE, Church.Status.DRAFT],
        )
        .distinct()
        .order_by("name", "id")
    )


def user_has_any_capability(user, capability):
    if not user.is_authenticated:
        return False
    if capability == CAP_SWITCH_CHURCH:
        return user.is_superuser and get_accessible_churches(user).count() > 1
    if user.is_superuser:
        return capability in ALL_CAPABILITIES
    return get_churches_for_capability(user, capability).exists()


def _redirect_without_church(request):
    if request.user.is_superuser:
        messages.warning(request, "Selectionnez une eglise pour continuer.")
        return redirect("select_church")

    if get_pending_invitations_for_user(request.user).exists():
        messages.info(
            request,
            "Consultez vos invitations en attente pour rejoindre une eglise.",
        )
        return redirect("pending_invitations")

    logout(request)
    messages.error(
        request,
        "Votre compte n'appartient a aucune eglise active et vous n'avez aucune invitation en attente. Contactez l'administration de l'eglise ou la plateforme.",
    )
    return redirect("home")


def require_capability(capability):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.is_superuser and capability in ALL_CAPABILITIES:
                return view_func(request, *args, **kwargs)

            church = getattr(request, "current_church", None)
            if church is None:
                church = get_selected_church(request, prefetch_pages=True)
                request.current_church = church

            if not church:
                return _redirect_without_church(request)

            if church.status in {Church.Status.SUSPENDED, Church.Status.ARCHIVED}:
                messages.error(request, "Cette eglise est suspendue ou archivee.")
                request.session.pop("active_church_id", None)
                return redirect("select_church")

            membership = getattr(request, "current_membership", None)
            if membership is None:
                membership = get_membership(request.user, church)
                request.current_membership = membership

            if not membership:
                messages.error(request, "Acces refuse. Aucun role defini pour cette eglise.")
                return redirect("select_church")

            capabilities = get_capabilities_for_user(request.user, membership)
            if capability not in capabilities:
                messages.error(request, "Acces refuse pour ce role.")
                return redirect("dashboard")

            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
