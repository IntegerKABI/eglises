from .models import Church


def get_accessible_churches(user):
    if not user.is_authenticated:
        return Church.objects.none()
    if user.is_superuser:
        return Church.objects.all()
    return Church.objects.filter(admin=user)


def get_selected_church(request):
    churches = get_accessible_churches(request.user)
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
