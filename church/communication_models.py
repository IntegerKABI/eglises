"""Communication, notification, audit, and background job models."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class ContactMessage(models.Model):
    """Store public contact form submissions for a church."""

    class Status(models.TextChoices):
        NEW = "new", "Nouveau"
        READ = "read", "Lu"
        RESPONDED = "responded", "Répondu"
        ARCHIVED = "archived", "Archivé"

    church = models.ForeignKey(
        "church.Church",
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Église",
    )
    sender_name = models.CharField(max_length=150, verbose_name="Nom")
    sender_email = models.EmailField(verbose_name="Email")
    subject = models.CharField(max_length=255, blank=True, verbose_name="Sujet")
    message = models.TextField(verbose_name="Message")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
        verbose_name="Statut",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_contact_messages",
        verbose_name="Assigné à",
    )
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name="Répondu le")
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responded_contact_messages",
        verbose_name="Répondu par",
    )
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name="Archivé le")
    is_read = models.BooleanField(default=False, verbose_name="Lu")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message de contact"
        verbose_name_plural = "Messages de contact"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["church", "status", "created_at"], name="cm_ch_stat_cr_idx"),
            models.Index(fields=["church", "is_read", "created_at"]),
            models.Index(fields=["assigned_to", "status"], name="cm_asg_stat_idx"),
        ]

    def __str__(self):
        return f"{self.sender_name} — {self.subject}"

    def save(self, *args, **kwargs):
        """Keep read state, status, and archive timestamp synchronized."""
        if not self.status:
            self.status = self.Status.READ if self.is_read else self.Status.NEW
        self.is_read = self.status != self.Status.NEW
        if self.status == self.Status.ARCHIVED and self.archived_at is None:
            self.archived_at = timezone.now()
        super().save(*args, **kwargs)


class ContactMessageReply(models.Model):
    """Store staff replies associated with a contact message."""

    message = models.ForeignKey(
        ContactMessage,
        on_delete=models.CASCADE,
        related_name="replies",
        verbose_name="Message",
    )
    body = models.TextField(verbose_name="Réponse")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_message_replies",
        verbose_name="Répondu par",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Réponse au message"
        verbose_name_plural = "Réponses aux messages"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["message", "created_at"], name="cmr_msg_cr_idx"),
        ]

    def __str__(self):
        return f"Réponse {self.pk} - {self.message_id}"


class Notification(models.Model):
    """Store dashboard notifications addressed to a user."""

    class Category(models.TextChoices):
        INVITE = "invite", "Invitation"
        ROLE = "role", "Changement de rôle"
        MESSAGE = "message", "Nouveau message"
        EVENT = "event", "Changement événement"
        SERMON = "sermon", "Changement prédication"

    church = models.ForeignKey(
        "church.Church",
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Église",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Destinataire",
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        db_index=True,
        verbose_name="Catégorie",
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    body = models.TextField(blank=True, verbose_name="Message")
    link = models.CharField(max_length=300, blank=True, verbose_name="Lien")
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="Lu")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"], name="notif_rec_read_cr_idx"),
            models.Index(fields=["church", "created_at"], name="notif_ch_cr_idx"),
        ]

    def __str__(self):
        return f"{self.get_category_display()} - {self.title}"


class AuditLog(models.Model):
    """Store immutable audit records for platform and tenant operations."""

    church = models.ForeignKey(
        "church.Church",
        on_delete=models.CASCADE,
        related_name="audit_logs",
        null=True,
        blank=True,
        verbose_name="Église",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Auteur",
    )
    action = models.CharField(max_length=50, db_index=True, verbose_name="Action")
    object_type = models.CharField(max_length=100, db_index=True, verbose_name="Type d'objet")
    object_id = models.CharField(max_length=64, blank=True, verbose_name="ID objet")
    object_repr = models.CharField(max_length=255, blank=True, verbose_name="Résumé")
    metadata = models.JSONField(blank=True, default=dict, verbose_name="Détails")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journaux d'audit"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["church", "created_at"], name="audit_ch_cr_idx"),
            models.Index(fields=["actor", "created_at"], name="audit_actor_cr_idx"),
            models.Index(fields=["object_type", "object_id"], name="audit_obj_idx"),
        ]

    def __str__(self):
        return f"{self.action} - {self.object_type} ({self.object_id})"


class BackgroundJob(models.Model):
    """Persist background jobs that must survive request and process boundaries."""

    class JobType(models.TextChoices):
        SEND_INVITE_EMAIL = "send_invite_email", "Envoi email invitation"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        RUNNING = "running", "En cours"
        COMPLETED = "completed", "Terminee"
        FAILED = "failed", "Echouee"

    job_type = models.CharField(
        max_length=50,
        choices=JobType.choices,
        db_index=True,
        verbose_name="Type de tache",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="Statut",
    )
    payload = models.JSONField(default=dict, verbose_name="Charge utile")
    attempts = models.PositiveIntegerField(default=0, verbose_name="Nombre d'essais")
    max_attempts = models.PositiveIntegerField(default=3, verbose_name="Essais maximum")
    available_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="Disponible le")
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name="Verrouille le")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Demarre le")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Termine le")
    last_error = models.TextField(blank=True, verbose_name="Derniere erreur")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tache d'arriere-plan"
        verbose_name_plural = "Taches d'arriere-plan"
        ordering = ["available_at", "id"]
        indexes = [
            models.Index(fields=["status", "available_at"], name="bg_job_status_avail_idx"),
            models.Index(fields=["job_type", "status"], name="bg_job_type_status_idx"),
        ]

    def __str__(self):
        return f"{self.job_type} ({self.status})"
