from django.db.models import Prefetch

from .models import Church, Page


def _menu_pages_queryset():
    return Page.objects.filter(is_active=True, is_in_menu=True).only(
        'id',
        'church_id',
        'slug',
        'title',
        'is_in_menu',
        'is_active',
    )


def get_accessible_churches(user, prefetch_pages=False):
    if not user.is_authenticated:
        return Church.objects.none()
    if user.is_superuser:
        churches = Church.objects.all()
    else:
        churches = Church.objects.filter(admin=user)
    if prefetch_pages:
        churches = churches.prefetch_related(
            Prefetch('pages', queryset=_menu_pages_queryset(), to_attr='menu_pages')
        )
    return churches


def get_selected_church(request, prefetch_pages=False):
    churches = get_accessible_churches(request.user, prefetch_pages=prefetch_pages)
    if not churches.exists():
        return None

    church_id = request.session.get('active_church_id')
    if church_id:
        church = churches.filter(id=church_id).first()
        if church:
            return church

    if churches.count() == 1:
        church = churches.first()
        request.session['active_church_id'] = church.id
        return church

    return None
