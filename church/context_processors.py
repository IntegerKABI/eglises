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

from .models import SiteSettings


def church_context(request):
    """
    Injecte l'Ã©glise courante dans tous les templates.
    
    L'Ã©glise est dÃ©terminÃ©e soit par :
    1. Le slug dans l'URL (ex: /eglise/demo/...)
    2. La sÃ©lection de l'utilisateur connectÃ©
    """
    church = getattr(request, 'current_church', None)

    site = SiteSettings.get()

    menu_pages = getattr(church, 'menu_pages', None) if church else None
    return {
        'current_church': church,
        'menu_pages': menu_pages,
        'app_name': site.site_name,
        'site_settings': site,
    }
