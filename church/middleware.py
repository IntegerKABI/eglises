from django.db.models import Prefetch

from .models import Church, Page, filter_public_queryset
from .tenancy import get_selected_church, get_membership


def _menu_pages_queryset():
    """Build the menu-page queryset so public pages can prefetch navigation once."""
    return filter_public_queryset(Page.objects.filter(is_in_menu=True)).only(
        'id',
        'church_id',
        'slug',
        'title',
        'is_in_menu',
        'is_active',
        'visibility',
        'published_at',
    )


class CurrentChurchMiddleware:
    """Attach the active church and membership to each request before views run."""

    def __init__(self, get_response):
        """Store the downstream handler so the middleware can delegate after setup."""
        self.get_response = get_response

    def __call__(self, request):
        """Pass the request through unchanged when Django invokes the middleware."""
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Resolve the current church context before the selected view executes."""
        request.current_church = None
        request.current_membership = None
        request.current_church_slug = view_kwargs.get('church_slug')

        if request.current_church_slug:
            request.current_church = (
                Church.objects.filter(status=Church.Status.ACTIVE, slug=request.current_church_slug)
                .prefetch_related(
                    Prefetch('pages', queryset=_menu_pages_queryset(), to_attr='menu_pages')
                )
                .first()
            )
            if request.user.is_authenticated and request.current_church:
                request.current_membership = get_membership(request.user, request.current_church)
            return None

        if request.user.is_authenticated:
            request.current_church = get_selected_church(request, prefetch_pages=True)
            if request.current_church:
                request.current_membership = get_membership(request.user, request.current_church)
        return None
