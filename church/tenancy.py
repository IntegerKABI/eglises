from django.db.models import Prefetch

from .models import Church, ChurchMembership, Page, filter_public_queryset


def _menu_pages_queryset():
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


def get_accessible_churches(user, prefetch_pages=False):
    if not user.is_authenticated:
        return Church.objects.none()
    if user.is_superuser:
        churches = Church.objects.all()
    else:
        churches = Church.objects.filter(
            memberships__user=user,
            memberships__is_active=True,
            status__in=[Church.Status.ACTIVE, Church.Status.DRAFT],
        ).distinct()
    churches = churches.order_by('name', 'id')
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
        request.session.pop('active_church_id', None)

    if churches.count() == 1:
        church = churches.first()
        request.session['active_church_id'] = church.id
        return church

    church = churches.first()
    if church:
        request.session['active_church_id'] = church.id
        return church

    return None


def get_membership(user, church):
    if not user.is_authenticated or not church:
        return None
    if user.is_superuser:
        return None
    return ChurchMembership.objects.filter(
        user=user,
        church=church,
        is_active=True,
    ).first()
