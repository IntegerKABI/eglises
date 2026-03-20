"""Domain models for the church application."""

from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.html import strip_tags

from .membership_policy import validate_single_church_membership
from .model_helpers import (
    CHURCH_PLAN_LIMITS,
    SITE_SETTINGS_CACHE_KEY,
    _default_invite_expiry,
    _generate_unique_slug,
    filter_public_queryset,
    upload_church_cover,
    upload_church_logo,
    upload_event_image,
    upload_member_photo,
    upload_page_image,
    upload_sermon_image,
    upload_site_asset,
)


class Church(models.Model):
    """Represent a church tenant hosted on the platform."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Brouillon'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspendue'
        ARCHIVED = 'archived', 'Archivée'

    class Plan(models.TextChoices):
        STARTER = 'starter', 'Starter'
        GROWTH = 'growth', 'Growth'
        SCALE = 'scale', 'Scale'

    name = models.CharField(
        max_length=255,
        verbose_name="Nom de l'église"
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name="Identifiant URL",
        help_text="Généré automatiquement à partir du nom. Ex: 'vie-nouvelle'"
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
        default='#2c3e50',
        verbose_name="Couleur principale",
        help_text="Code hexadécimal, ex: #2c3e50"
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#3498db',
        verbose_name="Couleur secondaire"
    )

    welcome_message = models.TextField(
        blank=True,
        verbose_name="Message d'accueil",
        help_text="Affiché sur la page d'accueil"
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
        verbose_name = "Église"
        verbose_name_plural = "Églises"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Generate a unique slug from the church name."""
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
        SECRETARY = 'secretary', "Secrétaire"

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
        unique_together = ['user', 'church']
        indexes = [
            models.Index(fields=['church', 'role', 'is_active'], name='chm_ch_role_active_idx'),
            models.Index(fields=['user', 'is_active'], name='chm_user_active_idx'),
        ]

    def __str__(self):
        return f"{self.user} — {self.church} ({self.get_role_display()})"

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
        ACCEPTED = 'accepted', 'Acceptée'
        DECLINED = 'declined', 'Refusée'
        REVOKED = 'revoked', 'Révoquée'
        EXPIRED = 'expired', 'Expirée'

    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='invitations',
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
        related_name='sent_church_invitations',
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
        related_name='accepted_church_invitations',
        verbose_name="Acceptée par",
    )

    class Meta:
        verbose_name = "Invitation d'église"
        verbose_name_plural = "Invitations d'église"
        indexes = [
            models.Index(fields=['church', 'status'], name='ch_inv_ch_status_idx'),
            models.Index(fields=['email', 'status'], name='ch_inv_email_status_idx'),
        ]

    def __str__(self):
        return f"{self.email} — {self.church} ({self.get_role_display()})"

    @property
    def is_expired(self):
        return self.expires_at and timezone.now() >= self.expires_at


class Event(models.Model):
    """Store a church event with publication and visibility controls."""
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name="Église"
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
        verbose_name="Créé par",
    )
    event_date = models.DateField(verbose_name="Date", db_index=True)
    event_time = models.TimeField(blank=True, null=True, verbose_name="Heure")
    end_date = models.DateField(blank=True, null=True, verbose_name="Date de fin")
    location = models.CharField(max_length=255, blank=True, verbose_name="Lieu")
    visibility = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('private', 'Privé'), ('draft', 'Brouillon')],
        default='public',
        verbose_name="Visibilité",
    )
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="Date de publication")
    is_featured = models.BooleanField(default=False, verbose_name="Mis en avant")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        ordering = ['-event_date']  # Les plus récents en premier
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
    """Store a sermon with media links and publishing controls."""
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='sermons',
        verbose_name="Église"
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    slug = models.SlugField(max_length=120, verbose_name="Identifiant URL")
    preacher = models.CharField(max_length=150, blank=True, verbose_name="Prédicateur")
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
        verbose_name="Créé par",
    )
    video_url = models.URLField(blank=True, verbose_name="Lien vidéo (YouTube)")
    audio_url = models.URLField(blank=True, verbose_name="Lien audio")
    sermon_date = models.DateField(blank=True, null=True, verbose_name="Date", db_index=True)
    bible_reference = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Référence biblique",
        help_text="Ex: Jean 3:16"
    )
    visibility = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('private', 'Privé'), ('draft', 'Brouillon')],
        default='public',
        verbose_name="Visibilité",
    )
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="Date de publication")
    is_featured = models.BooleanField(default=False, verbose_name="Mis en avant")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    views_count = models.PositiveIntegerField(default=0, verbose_name="Nombre de vues")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Prédication"
        verbose_name_plural = "Prédications"
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
    """Store member records for a church directory and operations workflow."""
    GENDER_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]

    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name="Église"
    )
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    address = models.CharField(max_length=500, blank=True, verbose_name="Adresse")
    birth_date = models.DateField(blank=True, null=True, verbose_name="Date de naissance")
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        verbose_name="Genre"
    )
    membership_date = models.DateField(blank=True, null=True, verbose_name="Date d'adhésion")
    department = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Département/Ministère"
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
        verbose_name="Consentement donné le",
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
                "directory_consent_source": "Précisez la source du consentement.",
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
    """Store a custom church page with publication controls."""
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='pages',
        verbose_name="Église"
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
        verbose_name="Créé par",
    )
    sort_order = models.IntegerField(default=0, verbose_name="Ordre d'affichage")
    is_in_menu = models.BooleanField(default=True, verbose_name="Afficher dans le menu")
    visibility = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('private', 'Privé'), ('draft', 'Brouillon')],
        default='public',
        verbose_name="Visibilité",
    )
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="Date de publication")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Page"
        verbose_name_plural = "Pages"
        ordering = ['sort_order']
        unique_together = ['church', 'slug']  # Un slug unique PAR église
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
    """Store public contact form submissions for a church."""
    class Status(models.TextChoices):
        NEW = 'new', 'Nouveau'
        READ = 'read', 'Lu'
        RESPONDED = 'responded', 'Répondu'
        ARCHIVED = 'archived', 'Archivé'

    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name="Église"
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
        verbose_name="Assigné à",
    )
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name="Répondu le")
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responded_contact_messages',
        verbose_name="Répondu par",
    )
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name="Archivé le")
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
        return f"{self.sender_name} — {self.subject}"

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
    body = models.TextField(verbose_name="Réponse")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_message_replies',
        verbose_name="Répondu par",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Réponse au message"
        verbose_name_plural = "Réponses aux messages"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['message', 'created_at'], name='cmr_msg_cr_idx'),
        ]

    def __str__(self):
        return f"Réponse {self.pk} - {self.message_id}"


class Notification(models.Model):
    class Category(models.TextChoices):
        INVITE = 'invite', 'Invitation'
        ROLE = 'role', 'Changement de rôle'
        MESSAGE = 'message', 'Nouveau message'
        EVENT = 'event', 'Changement événement'
        SERMON = 'sermon', 'Changement prédication'

    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Église",
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
        verbose_name="Église",
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
    object_repr = models.CharField(max_length=255, blank=True, verbose_name="Résumé")
    metadata = models.JSONField(blank=True, default=dict, verbose_name="Détails")
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
    """Store the singleton platform-wide site settings."""
    site_name = models.CharField(
        max_length=255,
        default='Église SaaS',
        verbose_name="Nom de la plateforme"
    )
    site_slogan = models.CharField(
        max_length=500,
        blank=True,
        default='Une plateforme web complète pour votre église.',
        verbose_name="Slogan"
    )
    site_description = models.TextField(
        blank=True,
        default='Paramétrez, personnalisez et publiez en quelques clics.',
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
        help_text="Affichée en arrière-plan sur la page d'accueil"
    )
    contact_email = models.EmailField(
        blank=True,
        verbose_name="Email de contact global"
    )

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

    @classmethod
    def get(cls):
        """Return the singleton instance, creating it with defaults when missing."""
        cached = cache.get(SITE_SETTINGS_CACHE_KEY)
        if cached:
            return cached
        obj, _ = cls.objects.get_or_create(pk=1)
        cache.set(SITE_SETTINGS_CACHE_KEY, obj)
        return obj

