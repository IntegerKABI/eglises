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

from .models import Church, SiteSettings
from .tenancy import get_selected_church


def church_context(request):
    """
    Injecte l'Ã©glise courante dans tous les templates.
    
    L'Ã©glise est dÃ©terminÃ©e soit par :
    1. Le slug dans l'URL (ex: /eglise/demo/...)
    2. La sÃ©lection de l'utilisateur connectÃ©
    """
    church = None
    churches = Church.objects.filter(is_active=True)

    # Essayer de trouver l'Ã©glise depuis l'URL
    church_slug = request.resolver_match.kwargs.get('church_slug') if request.resolver_match else None

    if church_slug:
        church = churches.filter(slug=church_slug).first()
    elif request.user.is_authenticated:
        church = get_selected_church(request)

    site = SiteSettings.get()

    return {
        'current_church': church,
        'all_churches': churches,
        'app_name': site.site_name,
        'site_settings': site,
    }
