"""Invitation application services for tenant onboarding workflows."""

from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from ..audit import log_audit_safely
from ..background_jobs import enqueue_invite_email_job
from ..limits import enforce_limits_for_model
from ..models import ChurchInvitation, ChurchMembership
from ..notifications import notify_church_admins, notify_user
from ..context.church import _mark_invite_notifications_read

@dataclass(frozen=True)
class InvitationAcceptanceResult:
    """Represent the outcome of an invitation acceptance flow."""

    invitation: ChurchInvitation
    membership: ChurchMembership


def create_invitation_from_form(*, request, actor, church, form) -> ChurchInvitation:
    """Create an invitation and emit the related tenant side effects."""
    with transaction.atomic():
        invite = form.instance
        invite.church = church
        invite.invited_by = getattr(form, "invited_by", None) or actor
        if invite.status == ChurchInvitation.Status.PENDING:
            enforce_limits_for_model(church, ChurchInvitation)
        invite.save()
        log_audit_safely(
            actor=actor,
            church=church,
            action="invite_create",
            instance=invite,
            metadata={"email": invite.email, "role": invite.role},
            error_message="Failed to log invite creation action",
        )

        notify_church_admins(
            church,
            category="invite",
            title="Invitation envoyée",
            body=f"{invite.email} - {invite.get_role_display()}",
            link=reverse("manage_users"),
            exclude=actor,
        )

        invited_user = get_user_model().objects.filter(email__iexact=invite.email).first()
        if invited_user:
            notify_user(
                invited_user,
                church,
                category="invite",
                title="Invitation à rejoindre l'église",
                body=f"Invitation pour {church.name} ({invite.get_role_display()}).",
                link=reverse("accept_invite", args=[invite.token]),
            )

        invite_url = request.build_absolute_uri(reverse("accept_invite", args=[invite.token]))
        enqueue_invite_email_job(invite, invite_url)

    return invite


def create_signup_user_from_form(*, form):
    """Create the invited user account from a validated signup form."""
    user = form.instance
    user.email = form.invite_email
    user.set_password(form.cleaned_data["password1"])
    user.save()
    return user


def revoke_invitation(*, actor, church, invite: ChurchInvitation) -> ChurchInvitation:
    """Revoke a pending invitation and notify tenant administrators."""
    with transaction.atomic():
        invite.status = ChurchInvitation.Status.REVOKED
        invite.save(update_fields=["status"])

        log_audit_safely(
            actor=actor,
            church=church,
            action="invite_revoke",
            instance=invite,
            metadata={"email": invite.email},
            error_message="Failed to log invite revoke action",
        )

        invited_user = get_user_model().objects.filter(email__iexact=invite.email).first()
        if invited_user:
            _mark_invite_notifications_read(invited_user, invite)

        notify_church_admins(
            church,
            category="invite",
            title="Invitation révoquée",
            body=f"{invite.email} - {invite.get_role_display()}",
            link=reverse("manage_users"),
            exclude=actor,
        )

    return invite


def resend_invitation(*, request, actor, church, invite: ChurchInvitation) -> ChurchInvitation:
    """Refresh a pending invitation expiry date and queue another delivery."""
    with transaction.atomic():
        invite.expires_at = timezone.now() + timedelta(days=7)
        invite.save(update_fields=["expires_at"])

        log_audit_safely(
            actor=actor,
            church=church,
            action="invite_resend",
            instance=invite,
            metadata={"email": invite.email},
            error_message="Failed to log invite resend action",
        )

        invite_url = request.build_absolute_uri(reverse("accept_invite", args=[invite.token]))
        enqueue_invite_email_job(invite, invite_url)

        notify_church_admins(
            church,
            category="invite",
            title="Invitation renvoyée",
            body=f"{invite.email} - {invite.get_role_display()}",
            link=reverse("manage_users"),
            exclude=actor,
        )

    return invite


def accept_invitation(*, actor, invite: ChurchInvitation) -> InvitationAcceptanceResult:
    """Activate or create a membership from a pending invitation."""
    with transaction.atomic():
        membership = (
            ChurchMembership.objects.select_for_update()
            .filter(user=actor, church=invite.church)
            .first()
        )
        if membership:
            new_role = invite.role
            if membership.role == ChurchMembership.Role.ADMIN and invite.role != ChurchMembership.Role.ADMIN:
                new_role = membership.role
            if membership.role != new_role:
                membership.role = new_role
            if not membership.is_active:
                enforce_limits_for_model(invite.church, ChurchMembership)
            membership.is_active = True
            membership.save(update_fields=["role", "is_active"])
        else:
            enforce_limits_for_model(invite.church, ChurchMembership)
            membership = ChurchMembership.objects.create(
                user=actor,
                church=invite.church,
                role=invite.role,
                is_active=True,
            )

        invite.status = ChurchInvitation.Status.ACCEPTED
        invite.accepted_at = timezone.now()
        invite.accepted_by = actor
        invite.save(update_fields=["status", "accepted_at", "accepted_by"])

        log_audit_safely(
            actor=actor,
            church=invite.church,
            action="invite_accept",
            instance=invite,
            metadata={"email": invite.email, "role": invite.role},
            error_message="Failed to log invite acceptance action",
        )

        notify_church_admins(
            invite.church,
            category="invite",
            title="Invitation acceptée",
            body=f"{actor.get_full_name() or actor.username} a rejoint l'église.",
            link=reverse("manage_users"),
            exclude=actor,
        )
        if invite.invited_by and invite.invited_by != actor:
            notify_user(
                invite.invited_by,
                invite.church,
                category="invite",
                title="Invitation acceptée",
                body=f"{actor.get_full_name() or actor.username} a accepté l'invitation.",
                link=reverse("manage_users"),
            )

        _mark_invite_notifications_read(actor, invite)

    return InvitationAcceptanceResult(invitation=invite, membership=membership)
