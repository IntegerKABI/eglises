"""Superadmin application services for tenant lifecycle management."""

from dataclasses import dataclass
import logging

from django.db import transaction
from django.urls import reverse

from .audit import log_audit
from .background_jobs import enqueue_invite_email_job
from .models import ChurchInvitation, ChurchMembership
from .notifications import Notification, notify_user
from .view_helpers import _schedule_safe_after_commit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SuperadminChurchCreateResult:
    """Represent the outcome of a superadmin church creation flow."""

    church: object
    invitation: object | None
    membership: object | None
    created_admin_user: object | None
    success_message: str


def _log_superadmin_church_action(*, actor, church, action, metadata=None) -> None:
    """Write a superadmin church audit entry and log failures."""
    try:
        log_audit(
            actor=actor,
            church=church,
            action=action,
            instance=church,
            metadata=metadata or {},
        )
    except Exception:
        logger.error("Failed to log superadmin church action", exc_info=True)


def create_church_from_form(*, request, actor, form) -> SuperadminChurchCreateResult:
    """Create a tenant church and perform the matching onboarding side effects."""
    church = form.instance
    admin_user = form.admin_user
    membership = None
    invitation = None

    with transaction.atomic():
        church.save()
        if form.create_new_admin:
            admin_user.set_password(form.cleaned_data["new_admin_password1"])
            admin_user.is_active = True
            admin_user.save()
            membership = ChurchMembership.objects.create(
                user=admin_user,
                church=church,
                role=ChurchMembership.Role.ADMIN,
                is_active=True,
            )
        else:
            invitation = ChurchInvitation.objects.create(
                church=church,
                email=admin_user.email.strip().lower(),
                role=ChurchMembership.Role.ADMIN,
                invited_by=actor,
            )

    def after_commit() -> None:
        _log_superadmin_church_action(
            actor=actor,
            church=church,
            action="tenant_create",
            metadata={"status": church.status, "plan": church.plan},
        )
        if membership is not None:
            try:
                log_audit(
                    actor=actor,
                    church=church,
                    action="tenant_assign_admin",
                    instance=membership,
                    metadata={
                        "user_id": admin_user.pk,
                        "username": admin_user.username,
                    },
                )
            except Exception:
                logger.error("Failed to log tenant admin assignment action", exc_info=True)
        if invitation is not None:
            try:
                log_audit(
                    actor=actor,
                    church=church,
                    action="tenant_invite_admin",
                    instance=invitation,
                    metadata={
                        "email": invitation.email,
                        "user_id": admin_user.pk,
                    },
                )
            except Exception:
                logger.error("Failed to log tenant admin invitation action", exc_info=True)

    _schedule_safe_after_commit(after_commit)

    success_message = "Église créée avec son premier administrateur."
    if invitation is not None:
        notify_user(
            admin_user,
            church,
            Notification.Category.INVITE,
            "Invitation à administrer une église",
            body=f"Vous avez été invité à administrer {church.name}.",
            link=reverse("accept_invite", args=[invitation.token]),
        )
        if request is not None:
            invite_url = request.build_absolute_uri(reverse("accept_invite", args=[invitation.token]))
            enqueue_invite_email_job(invitation, invite_url)
        success_message = "Église créée et invitation admin envoyée."

    return SuperadminChurchCreateResult(
        church=church,
        invitation=invitation,
        membership=membership,
        created_admin_user=admin_user,
        success_message=success_message,
    )


def update_church_profile_from_form(*, actor, form):
    """Update the tenant profile and record the profile audit entry."""
    church = form.save()
    _schedule_safe_after_commit(
        lambda: _log_superadmin_church_action(
            actor=actor,
            church=church,
            action="tenant_update",
            metadata={"section": "profile"},
        )
    )
    return church


def update_church_status_from_form(*, actor, form, previous_status: str):
    """Update the tenant lifecycle status and record the transition."""
    church = form.save()
    _schedule_safe_after_commit(
        lambda: _log_superadmin_church_action(
            actor=actor,
            church=church,
            action="tenant_status_update",
            metadata={
                "previous_status": previous_status,
                "new_status": church.status,
            },
        )
    )
    return church


def update_church_plan_from_form(*, actor, form, previous_limits):
    """Update the tenant plan configuration and record the change."""
    church = form.save()
    current_limits = {
        resource: church.get_plan_limit(resource)
        for resource in (
            "members",
            "events",
            "sermons",
            "pages",
            "users",
            "pending_invitations",
            "storage_mb",
            "message_retention_days",
            "notification_retention_days",
        )
    }
    _schedule_safe_after_commit(
        lambda: _log_superadmin_church_action(
            actor=actor,
            church=church,
            action="tenant_plan_update",
            metadata={
                "previous_plan": previous_limits,
                "current_plan": current_limits,
            },
        )
    )
    return church
