"""Tenant and platform configuration models for the church application."""

from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from ..cache import bump_site_cache_version
from ..membership_policy import validate_single_church_membership
from ..helpers.model import (
    CHURCH_PLAN_LIMITS,
    SITE_SETTINGS_CACHE_KEY,
    _default_invite_expiry,
    _generate_unique_slug,
    upload_church_cover,
    upload_church_logo,
    upload_site_asset,
)


INVITATION_STATUS_PENDING = "pending"


class ChurchInvitationQuerySet(models.QuerySet):
    """Provide lifecycle-aware invitation query helpers."""

    def pending(self):
        """Return invitations whose persisted state is pending."""
        return self.filter(status=INVITATION_STATUS_PENDING)

    def actionable(self):
        """Return pending invitations that are still valid for user actions."""
        return self.pending().filter(expires_at__gt=timezone.now())


class Church(models.Model):
    """Represent a church tenant hosted on the platform."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspendue"
        ARCHIVED = "archived", "Archivée"

    class Plan(models.TextChoices):
        STARTER = "starter", "Starter"
        GROWTH = "growth", "Growth"
        SCALE = "scale", "Scale"

    name = models.CharField(max_length=255, verbose_name="Nom de l'église")
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name="Identifiant URL",
        help_text="Généré automatiquement à partir du nom. Ex: 'vie-nouvelle'",
    )
    description = models.TextField(blank=True, verbose_name="Description")
    logo = models.ImageField(
        upload_to=upload_church_logo,
        blank=True,
        null=True,
        verbose_name="Logo",
    )
    cover_image = models.ImageField(
        upload_to=upload_church_cover,
        blank=True,
        null=True,
        verbose_name="Image de couverture",
    )
    address = models.CharField(max_length=500, blank=True, verbose_name="Adresse")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    country = models.CharField(max_length=100, default="RD Congo", verbose_name="Pays")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    facebook = models.URLField(blank=True, verbose_name="Facebook")
    youtube = models.URLField(blank=True, verbose_name="YouTube")
    instagram = models.URLField(blank=True, verbose_name="Instagram")
    primary_color = models.CharField(
        max_length=7,
        default="#2c3e50",
        verbose_name="Couleur principale",
        help_text="Code hexadécimal, ex: #2c3e50",
    )
    secondary_color = models.CharField(
        max_length=7,
        default="#3498db",
        verbose_name="Couleur secondaire",
    )
    welcome_message = models.TextField(
        blank=True,
        verbose_name="Message d'accueil",
        help_text="Affiché sur la page d'accueil",
    )
    service_times = models.TextField(
        blank=True,
        verbose_name="Horaires des cultes",
        help_text="Ex: Dimanche 09h-12h, Mercredi 18h-20h",
    )
    pastor_name = models.CharField(max_length=150, blank=True, verbose_name="Nom du pasteur")
    plan = models.CharField(
        max_length=20,
        choices=Plan.choices,
        default=Plan.STARTER,
        db_index=True,
        verbose_name="Plan",
    )
    max_members_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Limite membres personnalisee",
        help_text="Laissez vide pour utiliser la limite du plan.",
    )
    max_events_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Limite evenements personnalisee",
        help_text="Laissez vide pour utiliser la limite du plan.",
    )
    max_sermons_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Limite predications personnalisee",
        help_text="Laissez vide pour utiliser la limite du plan.",
    )
    max_pages_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Limite pages personnalisee",
        help_text="Laissez vide pour utiliser la limite du plan.",
    )
    max_users_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Limite utilisateurs personnalisee",
        help_text="Laissez vide pour utiliser la limite du plan.",
    )
    max_pending_invitations_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Limite invitations en attente personnalisee",
        help_text="Laissez vide pour utiliser la limite du plan.",
    )
    max_storage_mb_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Limite stockage personnalisee (Mo)",
        help_text="Laissez vide pour utiliser la limite du plan.",
    )
    message_retention_days_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Retention messages personnalisee (jours)",
        help_text="Laissez vide pour utiliser la retention du plan.",
    )
    notification_retention_days_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Retention notifications personnalisee (jours)",
        help_text="Laissez vide pour utiliser la retention du plan.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
        verbose_name="Statut",
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Église"
        verbose_name_plural = "Églises"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def has_active_admins(self, *, exclude_membership_id=None):
        """Return whether the tenant currently has at least one active admin membership."""
        if not self.pk:
            return False
        memberships = self.memberships.filter(
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )
        if exclude_membership_id is not None:
            memberships = memberships.exclude(pk=exclude_membership_id)
        return memberships.exists()

    def clean(self):
        """Reject active tenant states that do not have an active administrator."""
        super().clean()
        if self.pk and self.status == self.Status.ACTIVE and not self.has_active_admins():
            raise ValidationError("Une eglise active doit avoir au moins un administrateur actif.")

    def save(self, *args, **kwargs):
        """Generate a unique slug and enforce tenant lifecycle invariants."""
        queryset = Church.objects.all()
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        base_value = self.slug or self.name
        self.slug = _generate_unique_slug(
            base_value,
            queryset,
            self._meta.get_field("slug").max_length,
            "eglise",
        )
        self.is_active = self.status == self.Status.ACTIVE
        self.full_clean()
        super().save(*args, **kwargs)

    def get_plan_limit(self, resource):
        """Return the effective plan limit for a tenant resource."""
        plan_limits = CHURCH_PLAN_LIMITS.get(self.plan, {})
        override_map = {
            "members": self.max_members_override,
            "events": self.max_events_override,
            "sermons": self.max_sermons_override,
            "pages": self.max_pages_override,
            "users": self.max_users_override,
            "pending_invitations": self.max_pending_invitations_override,
            "storage_mb": self.max_storage_mb_override,
            "message_retention_days": self.message_retention_days_override,
            "notification_retention_days": self.notification_retention_days_override,
        }
        override = override_map.get(resource)
        if override is not None:
            return override
        return plan_limits.get(resource)


class ChurchMembership(models.Model):
    """Link a user to a church with an RBAC role."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrateur"
        STAFF = "staff", "Staff"
        SECRETARY = "secretary", "Secrétaire"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="church_memberships",
        verbose_name="Utilisateur",
    )
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Église",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
        verbose_name="Rôle",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Membre d'église"
        verbose_name_plural = "Membres d'église"
        unique_together = ["user", "church"]
        indexes = [
            models.Index(fields=["church", "role", "is_active"], name="chm_ch_role_active_idx"),
            models.Index(fields=["user", "is_active"], name="chm_user_active_idx"),
        ]

    def __str__(self):
        return f"{self.user} — {self.church} ({self.get_role_display()})"

    def _get_previous_membership(self):
        """Return the persisted membership state before the current mutation."""
        if not self.pk:
            return None
        return (
            type(self)
            .objects.select_related("church")
            .only("church_id", "role", "is_active", "church__status")
            .filter(pk=self.pk)
            .first()
        )

    def _validate_admin_transition(self):
        """Reject changes that would remove the last active admin from an active tenant."""
        previous_membership = self._get_previous_membership()
        if previous_membership is None:
            return
        if previous_membership.church.status != Church.Status.ACTIVE:
            return

        removes_active_admin = (
            previous_membership.role == self.Role.ADMIN
            and previous_membership.is_active
            and (
                self.church_id != previous_membership.church_id
                or self.role != self.Role.ADMIN
                or not self.is_active
            )
        )
        if not removes_active_admin:
            return
        if previous_membership.church.has_active_admins(exclude_membership_id=self.pk):
            return
        raise ValidationError("Au moins un administrateur actif est requis.")

    def clean(self):
        """Enforce membership and tenant admin invariants."""
        super().clean()
        if self.is_active:
            validate_single_church_membership(self.user, church=self.church)
        self._validate_admin_transition()

    def save(self, *args, **kwargs):
        """Validate and persist the membership mutation."""
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Reject deleting the last active admin from an active tenant."""
        if (
            self.pk
            and self.church.status == Church.Status.ACTIVE
            and self.role == self.Role.ADMIN
            and self.is_active
            and not self.church.has_active_admins(exclude_membership_id=self.pk)
        ):
            raise ValidationError("Au moins un administrateur actif est requis.")
        super().delete(*args, **kwargs)


class ChurchInvitation(models.Model):
    """Store a church membership invitation for an email address."""

    class Status(models.TextChoices):
        PENDING = INVITATION_STATUS_PENDING, "En attente"
        ACCEPTED = "accepted", "Acceptée"
        DECLINED = "declined", "Refusée"
        REVOKED = "revoked", "Révoquée"
        EXPIRED = "expired", "Expirée"

    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name="Église",
    )
    email = models.EmailField(verbose_name="Email")
    role = models.CharField(
        max_length=20,
        choices=ChurchMembership.Role.choices,
        default=ChurchMembership.Role.STAFF,
        verbose_name="Rôle",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_church_invitations",
        verbose_name="Invité par",
    )
    token = models.UUIDField(default=uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="Statut",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_invite_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_church_invitations",
        verbose_name="Acceptée par",
    )

    objects = ChurchInvitationQuerySet.as_manager()

    class Meta:
        verbose_name = "Invitation d'église"
        verbose_name_plural = "Invitations d'église"
        indexes = [
            models.Index(fields=["church", "status"], name="ch_inv_ch_status_idx"),
            models.Index(fields=["email", "status"], name="ch_inv_email_status_idx"),
        ]

    def __str__(self):
        return f"{self.email} — {self.church} ({self.get_role_display()})"

    @property
    def is_expired(self):
        """Return whether the invitation is no longer valid."""
        return self.expires_at and timezone.now() >= self.expires_at

    @property
    def effective_status(self):
        """Return the invitation lifecycle state with derived expiry applied."""
        if self.status == self.Status.PENDING and self.is_expired:
            return self.Status.EXPIRED
        return self.status

    @property
    def is_actionable(self):
        """Return whether the invitation can still be accepted or declined."""
        return self.effective_status == self.Status.PENDING


class SiteSettings(models.Model):
    """Store the singleton platform-wide site settings."""

    site_name = models.CharField(
        max_length=255,
        default="Église SaaS",
        verbose_name="Nom de la plateforme",
    )
    site_slogan = models.CharField(
        max_length=500,
        blank=True,
        default="Une plateforme web complète pour votre église.",
        verbose_name="Slogan",
    )
    site_description = models.TextField(
        blank=True,
        default="Paramétrez, personnalisez et publiez en quelques clics.",
        verbose_name="Description courte",
    )
    site_logo = models.ImageField(
        upload_to=upload_site_asset,
        blank=True,
        null=True,
        verbose_name="Logo de la plateforme",
    )
    cover_image = models.ImageField(
        upload_to=upload_site_asset,
        blank=True,
        null=True,
        verbose_name="Image de couverture",
        help_text="Affichée en arrière-plan sur la page d'accueil",
    )
    contact_email = models.EmailField(blank=True, verbose_name="Email de contact global")

    class Meta:
        verbose_name = "Paramètres du site"
        verbose_name_plural = "Paramètres du site"

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        """Force the singleton record to use the primary key value 1."""
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(SITE_SETTINGS_CACHE_KEY)
        bump_site_cache_version()

    @classmethod
    def get(cls):
        """Return the singleton instance, creating it with defaults when missing."""
        cached = cache.get(SITE_SETTINGS_CACHE_KEY)
        if cached:
            return cached
        obj, _ = cls.objects.get_or_create(pk=1)
        cache.set(SITE_SETTINGS_CACHE_KEY, obj)
        return obj
