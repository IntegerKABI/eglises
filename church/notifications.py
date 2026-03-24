"""Notification helpers for church workflows."""

from unicodedata import normalize

from .models import ChurchMembership, Notification
from .permissions import get_capabilities_for_user


def _membership_queryset(church):
    return ChurchMembership.objects.filter(church=church, is_active=True).select_related('user')


def recipients_for_capability(church, capability):
    recipients = []
    for membership in _membership_queryset(church):
        if capability in get_capabilities_for_user(membership.user, membership):
            recipients.append(membership.user)
    return recipients


def notify_user(user, church, category, title, body="", link=""):
    Notification.objects.create(
        recipient=user,
        church=church,
        category=category,
        title=title,
        body=body,
        link=link,
    )


def notify_users(users, church, category, title, body="", link="", exclude=None):
    excluded_ids = {exclude.id} if exclude else set()
    notifications = [
        Notification(
            recipient=user,
            church=church,
            category=category,
            title=title,
            body=body,
            link=link,
        )
        for user in users
        if user.id not in excluded_ids
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)


def notify_church_admins(church, category, title, body="", link="", exclude=None):
    admins = _membership_queryset(church).filter(role=ChurchMembership.Role.ADMIN)
    notify_users([m.user for m in admins], church, category, title, body, link, exclude=exclude)


def notify_message_recipients(church, category, title, body="", link="", exclude=None):
    users = recipients_for_capability(church, capability="manage_messages")
    notify_users(users, church, category, title, body, link, exclude=exclude)


def _normalize_notification_text(*parts):
    text = " ".join(part for part in parts if part)
    normalized = normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def _is_urgent_contact_message(*parts):
    text = _normalize_notification_text(*parts)
    return any(
        keyword in text
        for keyword in (
            "urgent",
            "urgence",
            "immediat",
            "important",
            "asap",
        )
    )


def notify_contact_recipients(church, category, title, body="", link="", source_text="", exclude=None):
    """Notify the primary contact recipients for an inbound public message."""
    secretaries = [
        membership.user
        for membership in _membership_queryset(church).filter(role=ChurchMembership.Role.SECRETARY)
    ]
    admins = [
        membership.user
        for membership in _membership_queryset(church).filter(role=ChurchMembership.Role.ADMIN)
    ]
    urgent = _is_urgent_contact_message(title, body, source_text)

    if secretaries:
        notify_users(secretaries, church, category, title, body, link, exclude=exclude)
        if urgent:
            notify_users(admins, church, category, title, body, link, exclude=exclude)
        return

    notify_users(admins, church, category, title, body, link, exclude=exclude)


def notify_event_recipients(church, category, title, body="", link="", exclude=None):
    users = recipients_for_capability(church, capability="manage_events")
    notify_users(users, church, category, title, body, link, exclude=exclude)


def notify_user_role_change(church, target_user, title, body="", link="", actor=None):
    notify_user(target_user, church, Notification.Category.ROLE, title, body, link)
    notify_church_admins(church, Notification.Category.ROLE, title, body, link, exclude=actor)
