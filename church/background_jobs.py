"""Durable background job enqueueing and processing helpers."""

from __future__ import annotations

from datetime import timedelta
import logging
import sys
from typing import Callable

from django.conf import settings
from django.core.mail import send_mail
from django.db import connection, transaction
from django.utils import timezone

from .models import BackgroundJob, ChurchInvitation

logger = logging.getLogger(__name__)

DEFAULT_JOB_LIMIT = 100
DEFAULT_RETRY_DELAY_MINUTES = 5
MAX_RETRY_DELAY_MINUTES = 60


def build_invite_email_payload(invitation: ChurchInvitation, invite_url: str) -> dict[str, object]:
    """Return the serialized payload for an invitation email job."""
    return {
        "invitation_id": invitation.pk,
        "invite_url": invite_url,
    }


def enqueue_background_job(
    job_type: str,
    payload: dict[str, object],
    *,
    max_attempts: int = 3,
) -> BackgroundJob:
    """Persist a background job and optionally run it eagerly in tests."""
    job = BackgroundJob.objects.create(
        job_type=job_type,
        payload=payload,
        max_attempts=max_attempts,
    )

    if _should_process_jobs_eagerly():
        transaction.on_commit(lambda: process_background_job_by_id(job.pk))

    return job


def enqueue_invite_email_job(invitation: ChurchInvitation, invite_url: str) -> BackgroundJob:
    """Persist an invitation email delivery job."""
    return enqueue_background_job(
        BackgroundJob.JobType.SEND_INVITE_EMAIL,
        build_invite_email_payload(invitation, invite_url),
    )


def claim_next_background_job() -> BackgroundJob | None:
    """Claim the next available job for processing."""
    now = timezone.now()
    with transaction.atomic():
        queryset = BackgroundJob.objects.filter(
            status=BackgroundJob.Status.PENDING,
            available_at__lte=now,
        ).order_by("available_at", "id")

        if connection.features.has_select_for_update:
            select_for_update_kwargs = {}
            if connection.features.has_select_for_update_skip_locked:
                select_for_update_kwargs["skip_locked"] = True
            queryset = queryset.select_for_update(**select_for_update_kwargs)

        job = queryset.first()
        if job is None:
            return None

        job.status = BackgroundJob.Status.RUNNING
        job.attempts += 1
        job.locked_at = now
        if job.started_at is None:
            job.started_at = now
        job.save(update_fields=["status", "attempts", "locked_at", "started_at", "updated_at"])
        return job


def process_pending_background_jobs(*, limit: int = DEFAULT_JOB_LIMIT) -> int:
    """Process up to the provided number of pending jobs."""
    processed = 0
    while processed < limit:
        job = claim_next_background_job()
        if job is None:
            break
        process_background_job(job)
        processed += 1
    return processed


def process_background_job_by_id(job_id: int) -> bool:
    """Load and process a single job by its primary key."""
    job = BackgroundJob.objects.filter(pk=job_id).first()
    if job is None or job.status == BackgroundJob.Status.COMPLETED:
        return False
    if job.status == BackgroundJob.Status.FAILED and job.attempts >= job.max_attempts:
        return False
    if job.status == BackgroundJob.Status.PENDING:
        claimed_job = claim_next_background_job_by_id(job.pk)
        if claimed_job is None:
            return False
        job = claimed_job
    return process_background_job(job)


def claim_next_background_job_by_id(job_id: int) -> BackgroundJob | None:
    """Claim a specific pending job for immediate processing."""
    now = timezone.now()
    with transaction.atomic():
        queryset = BackgroundJob.objects.filter(
            pk=job_id,
            status=BackgroundJob.Status.PENDING,
            available_at__lte=now,
        )

        if connection.features.has_select_for_update:
            queryset = queryset.select_for_update()

        job = queryset.first()
        if job is None:
            return None

        job.status = BackgroundJob.Status.RUNNING
        job.attempts += 1
        job.locked_at = now
        if job.started_at is None:
            job.started_at = now
        job.save(update_fields=["status", "attempts", "locked_at", "started_at", "updated_at"])
        return job


def process_background_job(job: BackgroundJob) -> bool:
    """Execute a claimed background job."""
    handler = JOB_HANDLERS.get(job.job_type)
    if handler is None:
        _mark_job_failed(job, RuntimeError(f"Unknown background job type: {job.job_type}"), final=True)
        return False

    try:
        handler(job)
    except Exception as exc:
        _mark_job_failed(job, exc)
        return False

    _mark_job_completed(job)
    return True


def _send_invite_email(invitation: ChurchInvitation, invite_url: str) -> None:
    """Send the church invitation email."""
    subject = f"Invitation a rejoindre {invitation.church.name}"
    message = (
        "Bonjour,\n\n"
        f"Vous avez ete invite a rejoindre {invitation.church.name} en tant que {invitation.get_role_display()}.\n"
        f"Pour accepter l'invitation, cliquez ici : {invite_url}\n\n"
        f"Cette invitation expirera le {invitation.expires_at:%d/%m/%Y %H:%M}.\n"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
        [invitation.email],
        fail_silently=False,
    )


def _handle_invite_email_job(job: BackgroundJob) -> None:
    """Process a queued invitation email delivery."""
    invitation_id = job.payload.get("invitation_id")
    invite_url = job.payload.get("invite_url")
    invitation = (
        ChurchInvitation.objects.select_related("church")
        .filter(pk=invitation_id)
        .first()
    )
    if invitation is None:
        logger.warning("Background job %s skipped because invitation %s no longer exists", job.pk, invitation_id)
        return
    if invitation.status != ChurchInvitation.Status.PENDING or invitation.is_expired:
        logger.info(
            "Background job %s skipped because invitation %s is no longer deliverable",
            job.pk,
            invitation.pk,
        )
        return
    _send_invite_email(invitation, str(invite_url))


JOB_HANDLERS: dict[str, Callable[[BackgroundJob], None]] = {
    BackgroundJob.JobType.SEND_INVITE_EMAIL: _handle_invite_email_job,
}


def _mark_job_completed(job: BackgroundJob) -> None:
    """Mark a job as completed."""
    now = timezone.now()
    BackgroundJob.objects.filter(pk=job.pk).update(
        status=BackgroundJob.Status.COMPLETED,
        completed_at=now,
        locked_at=None,
        last_error="",
        updated_at=now,
    )


def _mark_job_failed(job: BackgroundJob, exc: Exception, *, final: bool = False) -> None:
    """Record a failed job attempt and schedule retries when allowed."""
    now = timezone.now()
    status = BackgroundJob.Status.FAILED
    available_at = job.available_at
    if not final and job.attempts < job.max_attempts:
        status = BackgroundJob.Status.PENDING
        delay_minutes = min(
            MAX_RETRY_DELAY_MINUTES,
            DEFAULT_RETRY_DELAY_MINUTES * max(job.attempts, 1),
        )
        available_at = now + timedelta(minutes=delay_minutes)

    BackgroundJob.objects.filter(pk=job.pk).update(
        status=status,
        available_at=available_at,
        locked_at=None,
        last_error=str(exc),
        updated_at=now,
    )
    if "test" not in sys.argv:
        logger.error(
            "Background job %s failed for type %s",
            job.pk,
            job.job_type,
            exc_info=True,
        )


def _should_process_jobs_eagerly() -> bool:
    """Return whether jobs should be processed synchronously after commit."""
    return bool(getattr(settings, "BACKGROUND_JOBS_EAGER", False))
