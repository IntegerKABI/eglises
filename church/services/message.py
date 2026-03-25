"""Message application services for tenant contact workflows."""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from ..models import ContactMessageReply
from ..models import ContactMessage


@dataclass(frozen=True)
class MessageReplyResult:
    """Represent the result of storing a reply for a contact message."""

    message: ContactMessage
    reply: ContactMessageReply


def mark_message_as_read(message: ContactMessage) -> ContactMessage:
    """Mark a contact message as read when it is newly received."""
    if message.status == ContactMessage.Status.NEW:
        message.status = ContactMessage.Status.READ
        message.save(update_fields=["status", "is_read"])
    return message


def archive_message(message: ContactMessage) -> ContactMessage:
    """Archive a contact message and record its archive timestamp."""
    message.status = ContactMessage.Status.ARCHIVED
    message.archived_at = timezone.now()
    message.save(update_fields=["status", "archived_at", "is_read"])
    return message


def assign_message_to_user(*, message: ContactMessage, user) -> ContactMessage:
    """Assign a contact message to the given user."""
    message.assigned_to = user
    message.save(update_fields=["assigned_to"])
    return message


def unassign_message(message: ContactMessage) -> ContactMessage:
    """Clear any assignee from a contact message."""
    message.assigned_to = None
    message.save(update_fields=["assigned_to"])
    return message


def respond_to_message(*, actor, message: ContactMessage, reply_form) -> MessageReplyResult:
    """Persist a reply and update the contact message response metadata."""
    with transaction.atomic():
        reply = reply_form.save(commit=False)
        reply.message = message
        reply.created_by = actor
        reply.save()

        message.status = ContactMessage.Status.RESPONDED
        message.responded_at = timezone.now()
        message.responded_by = actor
        message.save(update_fields=["status", "responded_at", "responded_by", "is_read"])

    return MessageReplyResult(message=message, reply=reply)
