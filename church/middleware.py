from django.db.models import Prefetch

from .models import Church, Page
from .tenancy import get_selected_church, get_membership


def _menu_pages_queryset():
    return Page.objects.filter(is_active=True, is_in_menu=True).only(
        'id',
        'church_id',
        'slug',
        'title',
        'is_in_menu',
        'is_active',
    )


class CurrentChurchMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        request.current_church = None
        request.current_membership = None
        request.current_church_slug = view_kwargs.get('church_slug')

        if request.current_church_slug:
            request.current_church = (
                Church.objects.filter(is_active=True, slug=request.current_church_slug)
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
