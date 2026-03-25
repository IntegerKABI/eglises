"""Context processors shared across church templates."""

from ..limits import filter_notifications_for_retention
from ..models import Notification, SiteSettings
from ..permissions import (
    CAP_SWITCH_CHURCH,
    CAP_VIEW_AUDIT,
    get_capabilities_for_request,
    user_has_any_capability,
)
from ..tenancy import get_accessible_churches


def church_context(request):
    """Expose the current church context and shared UI state to templates."""
    church = getattr(request, 'current_church', None)
    site = SiteSettings.get()
    membership = getattr(request, 'current_membership', None)
    menu_pages = getattr(church, 'menu_pages', None) if church else None
    capabilities = get_capabilities_for_request(request)
    can_view_audit = user_has_any_capability(request.user, CAP_VIEW_AUDIT)
    can_switch_church = user_has_any_capability(request.user, CAP_SWITCH_CHURCH)
    unread_notifications_count = 0
    if request.user.is_authenticated:
        accessible_churches = list(get_accessible_churches(request.user))
        unread_notifications_count = filter_notifications_for_retention(
            Notification.objects.filter(
                recipient=request.user,
                is_read=False,
                church__in=accessible_churches,
            ),
            accessible_churches,
        ).count()
    return {
        'current_church': church,
        'current_membership': membership,
        'membership_role': membership.role if membership else None,
        'menu_pages': menu_pages,
        'capabilities': capabilities,
        'can_view_audit': can_view_audit,
        'can_switch_church': can_switch_church,
        'app_name': site.site_name,
        'site_settings': site,
        'unread_notifications_count': unread_notifications_count,
    }
