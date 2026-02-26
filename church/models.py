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

from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class Church(models.Model):
    """
    TABLE CENTRALE — Représente une église.
    
    Chaque église qui utilise la plateforme a une ligne ici.
    Le champ 'slug' sert d'identifiant dans l'URL.
    Exemple : /eglise/vie-nouvelle/ → slug = "vie-nouvelle"
    """
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
        upload_to='churches/logos/',
        blank=True,
        null=True,
        verbose_name="Logo"
    )
    cover_image = models.ImageField(
        upload_to='churches/covers/',
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

    # Administration
    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='churches',
        verbose_name="Administrateur"
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")
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
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


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
        upload_to='events/',
        blank=True,
        null=True,
        verbose_name="Image"
    )
    event_date = models.DateField(verbose_name="Date")
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

    def __str__(self):
        return f"{self.title} ({self.event_date})"


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
        upload_to='sermons/',
        blank=True,
        null=True,
        verbose_name="Image"
    )
    video_url = models.URLField(blank=True, verbose_name="Lien vidéo (YouTube)")
    audio_url = models.URLField(blank=True, verbose_name="Lien audio")
    sermon_date = models.DateField(blank=True, null=True, verbose_name="Date")
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
        upload_to='members/',
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
        upload_to='pages/',
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

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
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
        upload_to='site/',
        blank=True,
        null=True,
        verbose_name="Logo de la plateforme"
    )
    cover_image = models.ImageField(
        upload_to='site/',
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

    @classmethod
    def get(cls):
        """Retourne l'instance unique, ou en crée une avec les valeurs par défaut."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
