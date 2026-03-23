"""Membership application services for tenant user management flows."""

from dataclasses import dataclass
import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse

from .audit import log_audit
from .forms import ChurchMembershipAssignForm
from .limits import enforce_limits_for_model
from .models import ChurchMembership
from .notifications import notify_user_role_change
from .view_helpers import _schedule_safe_after_commit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MembershipAssignmentResult:
    """Represent the outcome of assigning a user to a church."""

    membership: ChurchMembership
    created: bool


def assign_membership_from_form(*, actor, church, form: ChurchMembershipAssignForm) -> MembershipAssignmentResult:
    """Create or reactivate a church membership from a validated assignment form."""
    with transaction.atomic():
        membership = form.save(church=church)
        created = bool(getattr(form, "created", False))
        action_title = "Accès accordé" if created else "Rôle mis à jour"
        audit_action = "membership_assign" if created else "membership_update"

        def after_commit() -> None:
            try:
                log_audit(
                    actor=actor,
                    church=church,
                    action=audit_action,
                    instance=membership,
                    metadata={"role": membership.role},
                )
            except Exception:
                logger.error("Failed to log membership assignment action", exc_info=True)

            notify_user_role_change(
                church,
                membership.user,
                title=action_title,
                body=f"Votre rôle pour {church.name} est maintenant {membership.get_role_display()}",
                link=reverse("dashboard"),
                actor=actor,
            )

        _schedule_safe_after_commit(after_commit)

    return MembershipAssignmentResult(membership=membership, created=created)


def set_membership_active_state(*, actor, church, membership_id: int, is_active: bool) -> ChurchMembership:
    """Activate or deactivate a church membership with invariant enforcement."""
    with transaction.atomic():
        membership = (
            ChurchMembership.objects.select_for_update()
            .select_related("user")
            .get(pk=membership_id, church=church)
        )

        if is_active and not membership.is_active:
            enforce_limits_for_model(church, ChurchMembership)

        membership.is_active = is_active
        membership.save(update_fields=["is_active"])
        status_label = "actif" if membership.is_active else "inactif"

        def after_commit() -> None:
            try:
                log_audit(
                    actor=actor,
                    church=church,
                    action="membership_status",
                    instance=membership,
                    metadata={"active": membership.is_active},
                )
            except Exception:
                logger.error("Failed to log membership status action", exc_info=True)

            notify_user_role_change(
                church,
                membership.user,
                title="Statut utilisateur mis à jour",
                body=f"Votre accès est maintenant {status_label} pour {church.name}.",
                link=reverse("dashboard"),
                actor=actor,
            )

        _schedule_safe_after_commit(after_commit)

    return membership


def transfer_admin_role(*, actor, church, current_membership_id: int, target_membership_id: int) -> ChurchMembership:
    """Transfer the admin role from one active membership to another."""
    with transaction.atomic():
        current_membership = (
            ChurchMembership.objects.select_for_update()
            .select_related("user")
            .get(pk=current_membership_id, church=church)
        )
        target = (
            ChurchMembership.objects.select_for_update()
            .select_related("user")
            .get(pk=target_membership_id, church=church)
        )

        target.role = ChurchMembership.Role.ADMIN
        target.is_active = True
        target.save(update_fields=["role", "is_active"])

        if current_membership.pk != target.pk:
            current_membership.role = ChurchMembership.Role.STAFF
            current_membership.save(update_fields=["role"])

        def after_commit() -> None:
            try:
                log_audit(
                    actor=actor,
                    church=church,
                    action="membership_transfer_admin",
                    instance=target,
                    metadata={"from_user": current_membership.user_id},
                )
            except Exception:
                logger.error("Failed to log admin transfer action", exc_info=True)

            notify_user_role_change(
                church,
                target.user,
                title="Administration transférée",
                body=f"Vous êtes maintenant administrateur de {church.name}.",
                link=reverse("manage_users"),
                actor=actor,
            )

            if current_membership.user_id != target.user_id:
                notify_user_role_change(
                    church,
                    current_membership.user,
                    title="Administration transférée",
                    body=f"Votre rôle est maintenant {current_membership.get_role_display()} pour {church.name}.",
                    link=reverse("manage_users"),
                    actor=actor,
                )

        _schedule_safe_after_commit(after_commit)

    return target


def update_membership(*, actor, church, membership_id: int, role: str, is_active: bool) -> ChurchMembership:
    """Update a church membership role or active state under row locking."""
    with transaction.atomic():
        membership = (
            ChurchMembership.objects.select_for_update()
            .select_related("user")
            .get(pk=membership_id, church=church)
        )
        previous_role = membership.role
        previous_active = membership.is_active

        if not previous_active and is_active:
            enforce_limits_for_model(church, ChurchMembership)

        membership.role = role
        membership.is_active = is_active
        membership.save(update_fields=["role", "is_active"])

        if membership.role != previous_role or membership.is_active != previous_active:
            status_label = "actif" if membership.is_active else "inactif"

            def after_commit() -> None:
                try:
                    log_audit(
                        actor=actor,
                        church=church,
                        action="membership_update",
                        instance=membership,
                        metadata={
                            "role": membership.role,
                            "active": membership.is_active,
                        },
                    )
                except Exception:
                    logger.error("Failed to log membership update action", exc_info=True)

                notify_user_role_change(
                    church,
                    membership.user,
                    title="Rôle mis à jour",
                    body=f"Rôle: {membership.get_role_display()} (statut: {status_label}).",
                    link=reverse("manage_users"),
                    actor=actor,
                )

            _schedule_safe_after_commit(after_commit)

    return membership
