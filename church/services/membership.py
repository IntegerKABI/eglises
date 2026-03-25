"""Membership application services for tenant user management flows."""

from dataclasses import dataclass

from django.db import transaction
from django.urls import reverse

from ..audit import log_audit_safely
from ..limits import enforce_limits_for_model
from ..models import ChurchMembership
from ..notifications import notify_user_role_change
from ..context.church import _schedule_safe_after_commit

@dataclass(frozen=True)
class MembershipAssignmentResult:
    """Represent the outcome of assigning a user to a church."""

    membership: ChurchMembership
    created: bool


@dataclass(frozen=True)
class ChurchUserCreationResult:
    """Represent the outcome of creating a church-scoped user account."""

    user: object
    membership: ChurchMembership


def create_church_user(*, actor, church, form) -> ChurchUserCreationResult:
    """Create a user and their first membership from a validated form."""
    with transaction.atomic():
        user = form.instance
        user.set_password(form.cleaned_data["password1"])
        enforce_limits_for_model(church, ChurchMembership)
        user.save()
        membership = ChurchMembership.objects.create(
            user=user,
            church=church,
            role=form.cleaned_data["role"],
            is_active=True,
        )

    return ChurchUserCreationResult(user=user, membership=membership)


def assign_membership(*, actor, church, user, role) -> MembershipAssignmentResult:
    """Create or reactivate a church membership for a resolved user."""
    with transaction.atomic():
        membership = (
            ChurchMembership.objects.select_for_update()
            .filter(user=user, church=church)
            .first()
        )
        created = membership is None
        if membership:
            if not membership.is_active:
                enforce_limits_for_model(church, ChurchMembership)
            membership.role = role
            membership.is_active = True
            membership.save(update_fields=["role", "is_active"])
        else:
            enforce_limits_for_model(church, ChurchMembership)
            membership = ChurchMembership.objects.create(
                user=user,
                church=church,
                role=role,
                is_active=True,
            )

        action_title = "AccÃ¨s accordÃ©" if created else "RÃ´le mis Ã  jour"
        audit_action = "membership_assign" if created else "membership_update"

        def after_commit() -> None:
            log_audit_safely(
                actor=actor,
                church=church,
                action=audit_action,
                instance=membership,
                metadata={"role": membership.role},
                error_message="Failed to log membership assignment action",
            )

            notify_user_role_change(
                church,
                membership.user,
                title=action_title,
                body=f"Votre rÃ´le pour {church.name} est maintenant {membership.get_role_display()}",
                link=reverse("dashboard"),
                actor=actor,
            )

        _schedule_safe_after_commit(after_commit)

    return MembershipAssignmentResult(membership=membership, created=created)


def assign_membership_from_form(*, actor, church, form) -> MembershipAssignmentResult:
    """Resolve a validated assignment form into the shared membership service."""
    return assign_membership(
        actor=actor,
        church=church,
        user=form.user,
        role=form.cleaned_data["role"],
    )


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
            log_audit_safely(
                actor=actor,
                church=church,
                action="membership_status",
                instance=membership,
                metadata={"active": membership.is_active},
                error_message="Failed to log membership status action",
            )

            notify_user_role_change(
                church,
                membership.user,
                title="Statut utilisateur mis Ã  jour",
                body=f"Votre accÃ¨s est maintenant {status_label} pour {church.name}.",
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
            log_audit_safely(
                actor=actor,
                church=church,
                action="membership_transfer_admin",
                instance=target,
                metadata={"from_user": current_membership.user_id},
                error_message="Failed to log admin transfer action",
            )

            notify_user_role_change(
                church,
                target.user,
                title="Administration transfÃ©rÃ©e",
                body=f"Vous Ãªtes maintenant administrateur de {church.name}.",
                link=reverse("manage_users"),
                actor=actor,
            )

            if current_membership.user_id != target.user_id:
                notify_user_role_change(
                    church,
                    current_membership.user,
                    title="Administration transfÃ©rÃ©e",
                    body=f"Votre rÃ´le est maintenant {current_membership.get_role_display()} pour {church.name}.",
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
                log_audit_safely(
                    actor=actor,
                    church=church,
                    action="membership_update",
                    instance=membership,
                    metadata={
                        "role": membership.role,
                        "active": membership.is_active,
                    },
                    error_message="Failed to log membership update action",
                )

                notify_user_role_change(
                    church,
                    membership.user,
                    title="RÃ´le mis Ã  jour",
                    body=f"RÃ´le: {membership.get_role_display()} (statut: {status_label}).",
                    link=reverse("manage_users"),
                    actor=actor,
                )

            _schedule_safe_after_commit(after_commit)

    return membership

