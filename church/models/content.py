"""Content and directory models for church tenant data."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.html import strip_tags

from ..helpers.model import (
    _generate_unique_slug,
    upload_event_image,
    upload_member_photo,
    upload_page_image,
    upload_sermon_image,
)


class Event(models.Model):
    """Store a church event with publication and visibility controls."""

    church = models.ForeignKey(
        "church.Church",
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Église",
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    slug = models.SlugField(max_length=120, verbose_name="Identifiant URL")
    description = models.TextField(blank=True, verbose_name="Description")
    image = models.ImageField(
        upload_to=upload_event_image,
        blank=True,
        null=True,
        verbose_name="Image",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_events",
        verbose_name="Créé par",
    )
    event_date = models.DateField(verbose_name="Date", db_index=True)
    event_time = models.TimeField(blank=True, null=True, verbose_name="Heure")
    end_date = models.DateField(blank=True, null=True, verbose_name="Date de fin")
    location = models.CharField(max_length=255, blank=True, verbose_name="Lieu")
    visibility = models.CharField(
        max_length=20,
        choices=[("public", "Public"), ("private", "Privé"), ("draft", "Brouillon")],
        default="public",
        verbose_name="Visibilité",
    )
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="Date de publication")
    is_featured = models.BooleanField(default=False, verbose_name="Mis en avant")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        ordering = ["-event_date"]
        indexes = [
            models.Index(fields=["church", "is_active", "event_date"]),
            models.Index(fields=["church", "is_featured"]),
            models.Index(fields=["church", "event_date"]),
            models.Index(fields=["church", "visibility", "published_at"], name="evt_ch_vis_pub_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["church", "slug"], name="uniq_event_church_slug"),
        ]

    def __str__(self):
        return f"{self.title} ({self.event_date})"

    def clean(self):
        """Ensure the optional end date does not precede the event date."""
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
        """Generate a church-scoped event slug before saving."""
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
        "church.Church",
        on_delete=models.CASCADE,
        related_name="sermons",
        verbose_name="Église",
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    slug = models.SlugField(max_length=120, verbose_name="Identifiant URL")
    preacher = models.CharField(max_length=150, blank=True, verbose_name="Prédicateur")
    description = models.TextField(blank=True, verbose_name="Description")
    image = models.ImageField(
        upload_to=upload_sermon_image,
        blank=True,
        null=True,
        verbose_name="Image",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sermons",
        verbose_name="Créé par",
    )
    video_url = models.URLField(blank=True, verbose_name="Lien vidéo (YouTube)")
    audio_url = models.URLField(blank=True, verbose_name="Lien audio")
    sermon_date = models.DateField(blank=True, null=True, verbose_name="Date", db_index=True)
    bible_reference = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Référence biblique",
        help_text="Ex: Jean 3:16",
    )
    visibility = models.CharField(
        max_length=20,
        choices=[("public", "Public"), ("private", "Privé"), ("draft", "Brouillon")],
        default="public",
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
        ordering = ["-sermon_date"]
        indexes = [
            models.Index(fields=["church", "is_active", "sermon_date"]),
            models.Index(fields=["church", "is_featured"]),
            models.Index(fields=["church", "sermon_date"]),
            models.Index(fields=["church", "visibility", "published_at"], name="serm_ch_vis_pub_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["church", "slug"], name="uniq_sermon_church_slug"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Generate a church-scoped sermon slug before saving."""
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
        ("M", "Masculin"),
        ("F", "Féminin"),
    ]

    church = models.ForeignKey(
        "church.Church",
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name="Église",
    )
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    address = models.CharField(max_length=500, blank=True, verbose_name="Adresse")
    birth_date = models.DateField(blank=True, null=True, verbose_name="Date de naissance")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, verbose_name="Genre")
    membership_date = models.DateField(blank=True, null=True, verbose_name="Date d'adhésion")
    department = models.CharField(max_length=100, blank=True, verbose_name="Département/Ministère")
    directory_consent = models.BooleanField(
        default=False,
        verbose_name="Consentement annuaire",
        help_text="Autorise l'affichage dans l'annuaire public.",
    )
    directory_consent_source = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Source du consentement",
    )
    directory_consent_at = models.DateTimeField(blank=True, null=True, verbose_name="Consentement donné le")
    photo = models.ImageField(
        upload_to=upload_member_photo,
        blank=True,
        null=True,
        verbose_name="Photo",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membre"
        verbose_name_plural = "Membres"
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["church", "is_active"]),
            models.Index(fields=["church", "gender"]),
            models.Index(fields=["church", "last_name", "first_name"]),
            models.Index(fields=["church", "directory_consent"], name="member_ch_cons_idx"),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def clean(self):
        """Require consent metadata when a member is public in the directory."""
        super().clean()
        if self.directory_consent and not self.directory_consent_source:
            raise ValidationError(
                {"directory_consent_source": "Précisez la source du consentement."}
            )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        """Maintain consent timestamps and source fields consistently."""
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
        "church.Church",
        on_delete=models.CASCADE,
        related_name="pages",
        verbose_name="Église",
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    slug = models.SlugField(max_length=100, verbose_name="Identifiant URL")
    content = models.TextField(blank=True, verbose_name="Contenu")
    image = models.ImageField(
        upload_to=upload_page_image,
        blank=True,
        null=True,
        verbose_name="Image",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_pages",
        verbose_name="Créé par",
    )
    sort_order = models.IntegerField(default=0, verbose_name="Ordre d'affichage")
    is_in_menu = models.BooleanField(default=True, verbose_name="Afficher dans le menu")
    visibility = models.CharField(
        max_length=20,
        choices=[("public", "Public"), ("private", "Privé"), ("draft", "Brouillon")],
        default="public",
        verbose_name="Visibilité",
    )
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="Date de publication")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Page"
        verbose_name_plural = "Pages"
        ordering = ["sort_order"]
        unique_together = ["church", "slug"]
        indexes = [
            models.Index(fields=["church", "is_active", "is_in_menu"]),
            models.Index(fields=["church", "sort_order"]),
            models.Index(fields=["church", "visibility", "published_at"], name="page_ch_vis_pub_idx"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Strip unsafe markup and generate a church-scoped page slug."""
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
