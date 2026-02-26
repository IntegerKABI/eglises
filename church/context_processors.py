"""
=================================================================
CONTEXT PROCESSORS — Variables disponibles dans TOUS les templates
=================================================================
Un context processor est une fonction qui injecte des variables 
dans TOUS les templates HTML automatiquement.

Ici, on injecte les infos de l'église courante pour que chaque 
page puisse afficher le nom, le logo, les couleurs, etc.
sans qu'on ait besoin de les passer manuellement dans chaque vue.
=================================================================
"""

from .models import Church, SiteSettings


def church_context(request):
    """
    Injecte l'église courante dans tous les templates.
    
    L'église est déterminée soit par :
    1. Le slug dans l'URL (ex: /eglise/demo/...)
    2. La session de l'utilisateur connecté
    3. La première église active (fallback pour le développement)
    """
    church = None
    churches = Church.objects.filter(is_active=True)

    # Essayer de trouver l'église depuis l'URL
    church_slug = request.resolver_match.kwargs.get('church_slug') if request.resolver_match else None

    if church_slug:
        church = churches.filter(slug=church_slug).first()
    elif request.user.is_authenticated and hasattr(request.user, 'churches'):
        church = request.user.churches.first()

    # Fallback : première église active
    if not church:
        church = churches.first()

    site = SiteSettings.get()

    return {
        'current_church': church,
        'all_churches': churches,
        'app_name': site.site_name,
        'site_settings': site,
    }
