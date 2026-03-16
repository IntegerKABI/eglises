from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import ChurchMembership
from .tenancy import get_membership, get_selected_church


def require_church_roles(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            church = getattr(request, 'current_church', None)
            if church is None:
                church = get_selected_church(request, prefetch_pages=True)
                request.current_church = church
            if not church:
                messages.warning(request, "Sélectionnez une église pour continuer.")
                return redirect('select_church')

            membership = getattr(request, 'current_membership', None)
            if membership is None:
                membership = get_membership(request.user, church)
                request.current_membership = membership

            if not membership:
                messages.error(request, "Accès refusé. Aucun rôle défini pour cette église.")
                return redirect('select_church')

            if roles and membership.role not in roles:
                messages.error(request, "Accès refusé pour ce rôle.")
                return redirect('dashboard')

            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


ADMIN_ONLY = (ChurchMembership.Role.ADMIN,)
STAFF_ROLES = (ChurchMembership.Role.ADMIN, ChurchMembership.Role.STAFF)
SECRETARY_ROLES = (ChurchMembership.Role.ADMIN, ChurchMembership.Role.SECRETARY)
MEMBER_ROLES = (
    ChurchMembership.Role.ADMIN,
    ChurchMembership.Role.STAFF,
    ChurchMembership.Role.SECRETARY,
)
