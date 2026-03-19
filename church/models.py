"""
=================================================================
MODÃˆLES â€” Structure de la base de donnÃ©es
=================================================================
Chaque classe = une table dans la base de donnÃ©es.
Chaque attribut = une colonne dans cette table.

Django crÃ©e automatiquement les tables Ã  partir de ces classes
grÃ¢ce aux commandes "makemigrations" et "migrate".

ARCHITECTURE :
- Church : la table centrale, chaque Ã©glise a sa propre config
- Event, Sermon, Member, etc. : liÃ©s Ã  une Ã©glise via church_id
=================================================================
"""

import os
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify

from .membership_policy import validate_single_church_membership


def _generate_unique_slug(base_value, queryset, max_length, fallback):
    base_slug = slugify(base_value) or fallback
    if max_length:
        base_slug = base_slug[:max_length]
    slug = base_slug
    counter = 2
    while queryset.filter(slug=slug).exists():
        suffix = f"-{counter}"
        trimmed = base_slug
        if max_length and len(base_slug) + len(suffix) > max_length:
            trimmed = base_slug[: max_length - len(suffix)]
        slug = f"{trimmed}{suffix}"
        counter += 1
    return slug


SITE_SETTINGS_CACHE_KEY = "site_settings:singleton:v1"


def _uuid_filename(filename):
    _, ext = os.path.splitext(filename)
    return f"{uuid4().hex}{ext.lower()}"


def upload_church_logo(instance, filename):
    return f"churches/logos/{_uuid_filename(filename)}"


def upload_church_cover(instance, filename):
    return f"churches/covers/{_uuid_filename(filename)}"


def upload_event_image(instance, filename):
    return f"events/{_uuid_filename(filename)}"


def upload_sermon_image(instance, filename):
    return f"sermons/{_uuid_filename(filename)}"


def upload_member_photo(instance, filename):
    return f"members/{_uuid_filename(filename)}"


def upload_page_image(instance, filename):
    return f"pages/{_uuid_filename(filename)}"


def upload_site_asset(instance, filename):
    return f"site/{_uuid_filename(filename)}"


def _default_invite_expiry():
    return timezone.now() + timedelta(days=7)


def filter_public_queryset(queryset):
    now = timezone.now()
    return queryset.filter(
        visibility='public',
        is_active=True,
    ).filter(
        Q(published_at__isnull=True) | Q(published_at__lte=now)
    )


CHURCH_PLAN_LIMITS = {
    "starter": {
        "members": 200,
        "events": 50,
        "sermons": 100,
        "pages": 12,
        "users": 5,
        "pending_invitations": 10,
        "storage_mb": 512,
        "message_retention_days": 90,
        "notification_retention_days": 30,
    },
    "growth": {
        "members": 1000,
        "events": 300,
        "sermons": 500,
        "pages": 40,
        "users": 20,
        "pending_invitations": 50,
        "storage_mb": 2048,
        "message_retention_days": 180,
        "notification_retention_days": 90,
    },
    "scale": {
        "members": None,
        "events": None,
        "sermons": None,
        "pages": None,
        "users": None,
        "pending_invitations": None,
        "storage_mb": 10240,
        "message_retention_days": 365,
        "notification_retention_days": 180,
    },
}


class Church(models.Model):
    """
    TABLE CENTRALE â€” ReprÃ©sente une Ã©glise.
    
    Chaque Ã©glise qui utilise la plateforme a une ligne ici.
    Le champ 'slug' sert d'identifiant dans l'URL.
    Exemple : /eglise/vie-nouvelle/ â†’ slug = "vie-nouvelle"
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Brouillon'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspendue'
        ARCHIVED = 'archived', 'ArchivÃ©e'

    class Plan(models.TextChoices):
        STARTER = 'starter', 'Starter'
        GROWTH = 'growth', 'Growth'
        SCALE = 'scale', 'Scale'

    name = models.CharField(
        max_length=255,
        verbose_name="Nom de l'Ã©glise"
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name="Identifiant URL",
        help_text="GÃ©nÃ©rÃ© automatiquement Ã  partir du nom. Ex: 'vie-nouvelle'"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    logo = models.ImageField(
        upload_to=upload_church_logo,
        blank=True,
        null=True,
        verbose_name="Logo"
    )
    cover_image = models.ImageField(
        upload_to=upload_church_cover,
        blank=True,
        null=True,
        verbose_name="Image de couverture"
    )

    # CoordonnÃ©es
    address = models.CharField(max_length=500, blank=True, verbose_name="Adresse")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    country = models.CharField(max_length=100, default="RD Congo", verbose_name="Pays")
    phone = models.CharField(max_length=50, blank=True, verbose_name="TÃ©lÃ©phone")
    email = models.EmailField(blank=True, verbose_name="Email")

    # RÃ©seaux sociaux
    facebook = models.URLField(blank=True, verbose_name="Facebook")
    youtube = models.URLField(blank=True, verbose_name="YouTube")
    instagram = models.URLField(blank=True, verbose_name="Instagram")

    # Personnalisation visuelle
    primary_color = models.CharField(
        max_length=7,
        default='#2c3e50',
        verbose_name="Couleur principale",
        help_text="Code hexadÃ©cimal, ex: #2c3e50"
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#3498db',
        verbose_name="Couleur secondaire"
    )

    # Contenu
    welcome_message = models.TextField(
        blank=True,
        verbose_name="Message d'accueil",
        help_text="AffichÃ© sur la page d'accueil"
    )
    service_times = models.TextField(
        blank=True,
        verbose_name="Horaires des cultes",
        help_text="Ex: Dimanche 09h-12h, Mercredi 18h-20h"
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
        verbose_name = "Ã‰glise"
        verbose_name_plural = "Ã‰glises"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """GÃ©nÃ¨re automatiquement le slug Ã  partir du nom."""
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
        super().save(*args, **kwargs)

    def get_plan_limit(self, resource):
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
    class Role(models.TextChoices):
        ADMIN = 'admin', "Administrateur"
        STAFF = 'staff', "Staff"
        SECRETARY = 'secretary', "SecrÃ©taire"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='church_memberships',
        verbose_name="Utilisateur",
    )
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name="Ã‰glise",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
        verbose_name="RÃ´le",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Membre d'Ã©glise"
        verbose_name_plural = "Membres d'Ã©glise"
        unique_together = ['user', 'church']
        indexes = [
            models.Index(fields=['church', 'role', 'is_active'], name='chm_ch_role_active_idx'),
            models.Index(fields=['user', 'is_active'], name='chm_user_active_idx'),
        ]

    def __str__(self):
        return f"{self.user} â€” {self.church} ({self.get_role_display()})"

    def clean(self):
        super().clean()
        if self.is_active:
            validate_single_church_membership(self.user, church=self.church)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ChurchInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        ACCEPTED = 'accepted', 'AcceptÃ©e'
        DECLINED = 'declined', 'RefusÃ©e'
        REVOKED = 'revoked', 'RÃ©voquÃ©e'
        EXPIRED = 'expired', 'ExpirÃ©e'

    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='invitations',
        verbose_name="Ã‰glise",
    )
    email = models.EmailField(verbose_name="Email")
    role = models.CharField(
        max_length=20,
        choices=ChurchMembership.Role.choices,
        default=ChurchMembership.Role.STAFF,
        verbose_name="RÃ´le",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_church_invitations',
        verbose_name="InvitÃ© par",
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
        related_name='accepted_church_invitations',
        verbose_name="AcceptÃ©e par",
    )

    class Meta:
        verbose_name = "Invitation d'Ã©glise"
        verbose_name_plural = "Invitations d'Ã©glise"
        indexes = [
            models.Index(fields=['church', 'status'], name='ch_inv_ch_status_idx'),
            models.Index(fields=['email', 'status'], name='ch_inv_email_status_idx'),
        ]

    def __str__(self):
        return f"{self.email} â€” {self.church} ({self.get_role_display()})"

    @property
    def is_expired(self):
        return self.expires_at and timezone.now() >= self.expires_at


class Event(models.Model):
    """
    Ã‰VÃ‰NEMENTS â€” Cultes spÃ©ciaux, sÃ©minaires, concerts, etc.
    Chaque Ã©vÃ©nement appartient Ã  UNE Ã©glise (ForeignKey).
    """
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,  # Si l'Ã©glise est supprimÃ©e, ses Ã©vÃ©nements aussi
        related_name='events',
        verbose_name="Ã‰glise"
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    slug = models.SlugField(max_length=120, verbose_name="Identifiant URL")
    description = models.TextField(blank=True, verbose_name="Description")
    image = models.ImageField(
        upload_to=upload_event_image,
        blank=True,
        null=True,
        verbose_name="Image"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_events',
        verbose_name="CrÃ©Ã© par",
    )
    event_date = models.DateField(verbose_name="Date", db_index=True)
    event_time = models.TimeField(blank=True, null=True, verbose_name="Heure")
    end_date = models.DateField(blank=True, null=True, verbose_name="Date de fin")
    location = models.CharField(max_length=255, blank=True, verbose_name="Lieu")
    visibility = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('private', 'PrivÃ©'), ('draft', 'Brouillon')],
        default='public',
        verbose_name="VisibilitÃ©",
    )
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="Date de publication")
    is_featured = models.BooleanField(default=False, verbose_name="Mis en avant")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ã‰vÃ©nement"
        verbose_name_plural = "Ã‰vÃ©nements"
        ordering = ['-event_date']  # Les plus rÃ©cents en premier
        indexes = [
            models.Index(fields=['church', 'is_active', 'event_date']),
            models.Index(fields=['church', 'is_featured']),
            models.Index(fields=['church', 'event_date']),
            models.Index(fields=['church', 'visibility', 'published_at'], name='evt_ch_vis_pub_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['church', 'slug'], name='uniq_event_church_slug'),
        ]

    def __str__(self):
        return f"{self.title} ({self.event_date})"

    def clean(self):
        super().clean()
        if self.end_date and self.event_date and self.end_date < self.event_date:
            raise ValidationError(
                {
                    "end_date": (
                        "La date de fin doit etre posterieure ou egale "
                        "a la date de l'evenement."
                    )
                }
            )

    def save(self, *args, **kwargs):
        queryset = Event.objects.filter(church=self.church)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        base_value = self.slug or self.title
        self.slug = _generate_unique_slug(
            base_value,
            queryset,
            self._meta.get_field("slug").max_length,
            "evenement",
        )
        super().save(*args, **kwargs)

class Sermon(models.Model):
    """
    PRÃ‰DICATIONS â€” Messages, enseignements, avec lien vidÃ©o/audio.
    """
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='sermons',
        verbose_name="Ã‰glise"
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    slug = models.SlugField(max_length=120, verbose_name="Identifiant URL")
    preacher = models.CharField(max_length=150, blank=True, verbose_name="PrÃ©dicateur")
    description = models.TextField(blank=True, verbose_name="Description")
    image = models.ImageField(
        upload_to=upload_sermon_image,
        blank=True,
        null=True,
        verbose_name="Image"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_sermons',
        verbose_name="CrÃ©Ã© par",
    )
    video_url = models.URLField(blank=True, verbose_name="Lien vidÃ©o (YouTube)")
    audio_url = models.URLField(blank=True, verbose_name="Lien audio")
    sermon_date = models.DateField(blank=True, null=True, verbose_name="Date", db_index=True)
    bible_reference = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="RÃ©fÃ©rence biblique",
        help_text="Ex: Jean 3:16"
    )
    visibility = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('private', 'PrivÃ©'), ('draft', 'Brouillon')],
        default='public',
        verbose_name="VisibilitÃ©",
    )
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="Date de publication")
    is_featured = models.BooleanField(default=False, verbose_name="Mis en avant")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    views_count = models.PositiveIntegerField(default=0, verbose_name="Nombre de vues")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "PrÃ©dication"
        verbose_name_plural = "PrÃ©dications"
        ordering = ['-sermon_date']
        indexes = [
            models.Index(fields=['church', 'is_active', 'sermon_date']),
            models.Index(fields=['church', 'is_featured']),
            models.Index(fields=['church', 'sermon_date']),
            models.Index(fields=['church', 'visibility', 'published_at'], name='serm_ch_vis_pub_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['church', 'slug'], name='uniq_sermon_church_slug'),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        queryset = Sermon.objects.filter(church=self.church)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        base_value = self.slug or self.title
        self.slug = _generate_unique_slug(
            base_value,
            queryset,
            self._meta.get_field("slug").max_length,
            "sermon",
        )
        super().save(*args, **kwargs)


class Member(models.Model):
    """
    MEMBRES â€” Registre des membres de l'Ã©glise.
    """
    GENDER_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'FÃ©minin'),
    ]

    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name="Ã‰glise"
    )
    first_name = models.CharField(max_length=100, verbose_name="PrÃ©nom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=50, blank=True, verbose_name="TÃ©lÃ©phone")
    address = models.CharField(max_length=500, blank=True, verbose_name="Adresse")
    birth_date = models.DateField(blank=True, null=True, verbose_name="Date de naissance")
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        verbose_name="Genre"
    )
    membership_date = models.DateField(blank=True, null=True, verbose_name="Date d'adhÃ©sion")
    department = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="DÃ©partement/MinistÃ¨re"
    )
    directory_consent = models.BooleanField(
        default=False,
        verbose_name="Consentement annuaire",
        help_text="Autorise l'affichage dans l'annuaire public."
    )
    directory_consent_source = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Source du consentement",
    )
    directory_consent_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Consentement donnÃ© le",
    )
    photo = models.ImageField(
        upload_to=upload_member_photo,
        blank=True,
        null=True,
        verbose_name="Photo"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membre"
        verbose_name_plural = "Membres"
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['church', 'is_active']),
            models.Index(fields=['church', 'gender']),
            models.Index(fields=['church', 'last_name', 'first_name']),
            models.Index(fields=['church', 'directory_consent'], name='member_ch_cons_idx'),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def clean(self):
        super().clean()
        if self.directory_consent and not self.directory_consent_source:
            raise ValidationError({
                "directory_consent_source": "PrÃ©cisez la source du consentement.",
            })

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        if self.directory_consent:
            if self.directory_consent_at is None:
                self.directory_consent_at = timezone.now()
        else:
            self.directory_consent_at = None
            self.directory_consent_source = ""
        super().save(*args, **kwargs)


class Page(models.Model):
    """
    PAGES DYNAMIQUES â€” Pages personnalisables (Ã€ propos, MinistÃ¨res, etc.)
    Chaque Ã©glise peut crÃ©er ses propres pages.
    """
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='pages',
        verbose_name="Ã‰glise"
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    slug = models.SlugField(max_length=100, verbose_name="Identifiant URL")
    content = models.TextField(blank=True, verbose_name="Contenu")
    image = models.ImageField(
        upload_to=upload_page_image,
        blank=True,
        null=True,
        verbose_name="Image"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_pages',
        verbose_name="CrÃ©Ã© par",
    )
    sort_order = models.IntegerField(default=0, verbose_name="Ordre d'affichage")
    is_in_menu = models.BooleanField(default=True, verbose_name="Afficher dans le menu")
    visibility = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('private', 'PrivÃ©'), ('draft', 'Brouillon')],
        default='public',
        verbose_name="VisibilitÃ©",
    )
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="Date de publication")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Page"
        verbose_name_plural = "Pages"
        ordering = ['sort_order']
        unique_together = ['church', 'slug']  # Un slug unique PAR Ã©glise
        indexes = [
            models.Index(fields=['church', 'is_active', 'is_in_menu']),
            models.Index(fields=['church', 'sort_order']),
            models.Index(fields=['church', 'visibility', 'published_at'], name='page_ch_vis_pub_idx'),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.content:
            self.content = strip_tags(self.content)
        queryset = Page.objects.filter(church=self.church)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        base_value = self.slug or self.title
        self.slug = _generate_unique_slug(
            base_value,
            queryset,
            self._meta.get_field("slug").max_length,
            "page",
        )
        super().save(*args, **kwargs)


class ContactMessage(models.Model):
    """
    MESSAGES DE CONTACT â€” ReÃ§us via le formulaire du site public.
    """
    class Status(models.TextChoices):
        NEW = 'new', 'Nouveau'
        READ = 'read', 'Lu'
        RESPONDED = 'responded', 'RÃ©pondu'
        ARCHIVED = 'archived', 'ArchivÃ©'

    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name="Ã‰glise"
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
        related_name='assigned_contact_messages',
        verbose_name="AssignÃ© Ã ",
    )
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name="RÃ©pondu le")
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responded_contact_messages',
        verbose_name="RÃ©pondu par",
    )
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name="ArchivÃ© le")
    is_read = models.BooleanField(default=False, verbose_name="Lu")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message de contact"
        verbose_name_plural = "Messages de contact"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['church', 'status', 'created_at'], name='cm_ch_stat_cr_idx'),
            models.Index(fields=['church', 'is_read', 'created_at']),
            models.Index(fields=['assigned_to', 'status'], name='cm_asg_stat_idx'),
        ]

    def __str__(self):
        return f"{self.sender_name} â€” {self.subject}"

    def save(self, *args, **kwargs):
        if not self.status:
            self.status = self.Status.READ if self.is_read else self.Status.NEW
        self.is_read = self.status != self.Status.NEW
        if self.status == self.Status.ARCHIVED and self.archived_at is None:
            self.archived_at = timezone.now()
        super().save(*args, **kwargs)


class ContactMessageReply(models.Model):
    message = models.ForeignKey(
        ContactMessage,
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name="Message",
    )
    body = models.TextField(verbose_name="RÃ©ponse")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_message_replies',
        verbose_name="RÃ©pondu par",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "RÃ©ponse au message"
        verbose_name_plural = "RÃ©ponses aux messages"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['message', 'created_at'], name='cmr_msg_cr_idx'),
        ]

    def __str__(self):
        return f"RÃ©ponse {self.pk} - {self.message_id}"


class Notification(models.Model):
    class Category(models.TextChoices):
        INVITE = 'invite', 'Invitation'
        ROLE = 'role', 'Changement de rÃ´le'
        MESSAGE = 'message', 'Nouveau message'
        EVENT = 'event', 'Changement Ã©vÃ©nement'
        SERMON = 'sermon', 'Changement prÃ©dication'

    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Ã‰glise",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Destinataire",
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        db_index=True,
        verbose_name="CatÃ©gorie",
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    body = models.TextField(blank=True, verbose_name="Message")
    link = models.CharField(max_length=300, blank=True, verbose_name="Lien")
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="Lu")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'created_at'], name='notif_rec_read_cr_idx'),
            models.Index(fields=['church', 'created_at'], name='notif_ch_cr_idx'),
        ]

    def __str__(self):
        return f"{self.get_category_display()} - {self.title}"


class AuditLog(models.Model):
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        null=True,
        blank=True,
        verbose_name="Ã‰glise",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name="Auteur",
    )
    action = models.CharField(max_length=50, db_index=True, verbose_name="Action")
    object_type = models.CharField(max_length=100, db_index=True, verbose_name="Type d'objet")
    object_id = models.CharField(max_length=64, blank=True, verbose_name="ID objet")
    object_repr = models.CharField(max_length=255, blank=True, verbose_name="RÃ©sumÃ©")
    metadata = models.JSONField(blank=True, default=dict, verbose_name="DÃ©tails")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journaux d'audit"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['church', 'created_at'], name='audit_ch_cr_idx'),
            models.Index(fields=['actor', 'created_at'], name='audit_actor_cr_idx'),
            models.Index(fields=['object_type', 'object_id'], name='audit_obj_idx'),
        ]

    def __str__(self):
        return f"{self.action} - {self.object_type} ({self.object_id})"


class SiteSettings(models.Model):
    """
    PARAMÃˆTRES GLOBAUX DE LA PLATEFORME (singleton).
    
    Une seule ligne dans cette table, modifiable par le super-admin.
    Contient le nom de la plateforme, le slogan, etc.
    """
    site_name = models.CharField(
        max_length=255,
        default='Ã‰glise SaaS',
        verbose_name="Nom de la plateforme"
    )
    site_slogan = models.CharField(
        max_length=500,
        blank=True,
        default='Une plateforme web complÃ¨te pour votre Ã©glise.',
        verbose_name="Slogan"
    )
    site_description = models.TextField(
        blank=True,
        default='ParamÃ©trez, personnalisez et publiez en quelques clics.',
        verbose_name="Description courte"
    )
    site_logo = models.ImageField(
        upload_to=upload_site_asset,
        blank=True,
        null=True,
        verbose_name="Logo de la plateforme"
    )
    cover_image = models.ImageField(
        upload_to=upload_site_asset,
        blank=True,
        null=True,
        verbose_name="Image de couverture",
        help_text="AffichÃ©e en arriÃ¨re-plan sur la page d'accueil"
    )
    contact_email = models.EmailField(
        blank=True,
        verbose_name="Email de contact global"
    )

    class Meta:
        verbose_name = "ParamÃ¨tres du site"
        verbose_name_plural = "ParamÃ¨tres du site"

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        """Force l'ID Ã  1 pour garantir une seule ligne (singleton)."""
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    @classmethod
    def get(cls):
        """Retourne l'instance unique, ou en crÃ©e une avec les valeurs par dÃ©faut."""
        cached = cache.get(SITE_SETTINGS_CACHE_KEY)
        if cached:
            return cached
        obj, _ = cls.objects.get_or_create(pk=1)
        cache.set(SITE_SETTINGS_CACHE_KEY, obj)
        return obj

