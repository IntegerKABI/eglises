"""
=================================================================
MODÈLES — Structure de la base de données
=================================================================
Chaque classe = une table dans la base de données.
Chaque attribut = une colonne dans cette table.

Django crée automatiquement les tables à partir de ces classes
grâce aux commandes "makemigrations" et "migrate".

ARCHITECTURE :
- Church : la table centrale, chaque église a sa propre config
- Event, Sermon, Member, etc. : liés à une église via church_id
=================================================================
"""

import os
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify


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


class Church(models.Model):
    """
    TABLE CENTRALE — Représente une église.
    
    Chaque église qui utilise la plateforme a une ligne ici.
    Le champ 'slug' sert d'identifiant dans l'URL.
    Exemple : /eglise/vie-nouvelle/ → slug = "vie-nouvelle"
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Brouillon'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspendue'
        ARCHIVED = 'archived', 'Archivée'

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

    # Coordonnées
    address = models.CharField(max_length=500, blank=True, verbose_name="Adresse")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    country = models.CharField(max_length=100, default="RD Congo", verbose_name="Pays")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")

    # Réseaux sociaux
    facebook = models.URLField(blank=True, verbose_name="Facebook")
    youtube = models.URLField(blank=True, verbose_name="YouTube")
    instagram = models.URLField(blank=True, verbose_name="Instagram")

    # Personnalisation visuelle
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

    # Contenu
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
        """Génère automatiquement le slug à partir du nom."""
        if not self.slug:
            queryset = Church.objects.all()
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)
            self.slug = _generate_unique_slug(
                self.name,
                queryset,
                self._meta.get_field("slug").max_length,
                "eglise",
            )
        self.is_active = self.status == self.Status.ACTIVE
        super().save(*args, **kwargs)


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


class ChurchInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        ACCEPTED = 'accepted', 'Acceptée'
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
    """
    ÉVÉNEMENTS — Cultes spéciaux, séminaires, concerts, etc.
    Chaque événement appartient à UNE église (ForeignKey).
    """
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,  # Si l'église est supprimée, ses événements aussi
        related_name='events',
        verbose_name="Église"
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    image = models.ImageField(
        upload_to=upload_event_image,
        blank=True,
        null=True,
        verbose_name="Image"
    )
    event_date = models.DateField(verbose_name="Date", db_index=True)
    event_time = models.TimeField(blank=True, null=True, verbose_name="Heure")
    end_date = models.DateField(blank=True, null=True, verbose_name="Date de fin")
    location = models.CharField(max_length=255, blank=True, verbose_name="Lieu")
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

class Sermon(models.Model):
    """
    PRÉDICATIONS — Messages, enseignements, avec lien vidéo/audio.
    """
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name='sermons',
        verbose_name="Église"
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    preacher = models.CharField(max_length=150, blank=True, verbose_name="Prédicateur")
    description = models.TextField(blank=True, verbose_name="Description")
    image = models.ImageField(
        upload_to=upload_sermon_image,
        blank=True,
        null=True,
        verbose_name="Image"
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
        ]

    def __str__(self):
        return self.title


class Member(models.Model):
    """
    MEMBRES — Registre des membres de l'église.
    """
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
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Page(models.Model):
    """
    PAGES DYNAMIQUES — Pages personnalisables (À propos, Ministères, etc.)
    Chaque église peut créer ses propres pages.
    """
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
    sort_order = models.IntegerField(default=0, verbose_name="Ordre d'affichage")
    is_in_menu = models.BooleanField(default=True, verbose_name="Afficher dans le menu")
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
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.content:
            self.content = strip_tags(self.content)
        if not self.slug:
            queryset = Page.objects.filter(church=self.church)
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)
            self.slug = _generate_unique_slug(
                self.title,
                queryset,
                self._meta.get_field("slug").max_length,
                "page",
            )
        super().save(*args, **kwargs)


class ContactMessage(models.Model):
    """
    MESSAGES DE CONTACT — Reçus via le formulaire du site public.
    """
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
    is_read = models.BooleanField(default=False, verbose_name="Lu")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message de contact"
        verbose_name_plural = "Messages de contact"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['church', 'is_read', 'created_at']),
        ]

    def __str__(self):
        return f"{self.sender_name} — {self.subject}"


class SiteSettings(models.Model):
    """
    PARAMÈTRES GLOBAUX DE LA PLATEFORME (singleton).
    
    Une seule ligne dans cette table, modifiable par le super-admin.
    Contient le nom de la plateforme, le slogan, etc.
    """
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
        """Force l'ID à 1 pour garantir une seule ligne (singleton)."""
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    @classmethod
    def get(cls):
        """Retourne l'instance unique, ou en crée une avec les valeurs par défaut."""
        cached = cache.get(SITE_SETTINGS_CACHE_KEY)
        if cached:
            return cached
        obj, _ = cls.objects.get_or_create(pk=1)
        cache.set(SITE_SETTINGS_CACHE_KEY, obj)
        return obj
