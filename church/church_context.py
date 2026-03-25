"""Church resolution and after-commit helpers used by multiple view layers."""

import logging
import sys

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404

from .membership_policy import get_pending_invitations_for_user
from .models import Church, Notification
from .tenancy import get_membership, get_selected_church

logger = logging.getLogger(__name__)


def _mark_invite_notifications_read(user, invite):
    """Mark invitation-related notifications as read for a specific user."""
    Notification.objects.filter(
        recipient=user,
        church=invite.church,
        category=Notification.Category.INVITE,
        is_read=False,
    ).filter(
        Q(link__icontains=str(invite.token)) | Q(title__icontains="Invitation")
    ).update(is_read=True)


def _has_pending_invitations(user):
    """Return whether the user still has actionable pending invitations."""
    return get_pending_invitations_for_user(user).exists()


def _schedule_safe_after_commit(callback):
    """Run a callback after commit without spawning background threads."""
    running_tests = "test" in sys.argv

    def run_callback():
        try:
            callback()
        except Exception:
            if not running_tests:
                logger.error("Failed to execute after-commit callback", exc_info=True)

    if running_tests:
        run_callback()
        return

    transaction.on_commit(run_callback)


def _require_church(request):
    """Resolve the active church for dashboard and management requests."""
    church = getattr(request, 'current_church', None)
    if church is None:
        church = get_selected_church(request, prefetch_pages=True)
        request.current_church = church
    if not church:
        messages.warning(request, "Sélectionnez une église pour continuer.")
        return None
    if request.user.is_authenticated and not request.user.is_superuser:
        membership = getattr(request, 'current_membership', None)
        if membership is None:
            membership = get_membership(request.user, church)
            request.current_membership = membership
        if not membership:
            messages.error(request, "Accès refusé. Aucun rôle défini pour cette église.")
            return None
        if church.status in {Church.Status.SUSPENDED, Church.Status.ARCHIVED}:
            messages.error(request, "Cette église est suspendue ou archivée.")
            request.session.pop('active_church_id', None)
            return None
    return church


def _get_public_church(request, church_slug):
    """Resolve a public church page while preserving the current request cache."""
    church = getattr(request, 'current_church', None)
    current_slug = getattr(request, 'current_church_slug', None)
    if current_slug == church_slug:
        if church is None:
            raise Http404("Église introuvable.")
        return church
    return get_object_or_404(Church, slug=church_slug, status=Church.Status.ACTIVE)
