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


def get_accessible_church_count(request):
    count = getattr(request, "accessible_church_count", None)
    if count is not None:
        return count
    count = get_accessible_churches(request.user).count()
    request.accessible_church_count = count
    return count


def get_selected_church(request, prefetch_pages=False):
    churches = get_accessible_churches(request.user, prefetch_pages=prefetch_pages)
    church_count = churches.count()
    request.accessible_church_count = church_count
    if church_count == 0:
        request.session.pop('active_church_id', None)
        return None

    if not request.user.is_superuser and church_count > 1:
        request.session.pop('active_church_id', None)
        return None

    church_id = request.session.get('active_church_id')
    if church_id:
        church = churches.filter(id=church_id).first()
        if church:
            return church
        request.session.pop('active_church_id', None)

    if church_count == 1:
        church = churches.first()
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
