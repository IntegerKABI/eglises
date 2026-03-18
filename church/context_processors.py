"""
=================================================================
CONTEXT PROCESSORS â€” Variables disponibles dans TOUS les templates
=================================================================
Un context processor est une fonction qui injecte des variables 
dans TOUS les templates HTML automatiquement.

Ici, on injecte les infos de l'Ã©glise courante pour que chaque 
page puisse afficher le nom, le logo, les couleurs, etc.
sans qu'on ait besoin de les passer manuellement dans chaque vue.
=================================================================
"""

from .models import ChurchMembership, Notification, SiteSettings
from .permissions import get_capabilities_for_request
from .tenancy import get_accessible_church_count


def church_context(request):
    """
    Injecte l'Ã©glise courante dans tous les templates.
    
    L'Ã©glise est dÃ©terminÃ©e soit par :
    1. Le slug dans l'URL (ex: /eglise/demo/...)
    2. La sÃ©lection de l'utilisateur connectÃ©
    """
    church = getattr(request, 'current_church', None)

    site = SiteSettings.get()

    membership = getattr(request, 'current_membership', None)
    menu_pages = getattr(church, 'menu_pages', None) if church else None
    capabilities = get_capabilities_for_request(request)
    can_view_audit = False
    can_switch_church = False
    if request.user.is_authenticated:
        can_switch_church = get_accessible_church_count(request) > 1
        if request.user.is_superuser:
            can_view_audit = True
        else:
            can_view_audit = ChurchMembership.objects.filter(
                user=request.user,
                role=ChurchMembership.Role.ADMIN,
                is_active=True,
            ).exists()
    unread_notifications_count = 0
    if request.user.is_authenticated:
        unread_notifications_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
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
