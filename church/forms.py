"""
=================================================================
FORMULAIRES — Validation et affichage des formulaires
=================================================================
Django génère automatiquement les formulaires à partir des modèles.
On les personnalise ici pour :
- Choisir quels champs afficher
- Ajouter des widgets HTML (datepicker, textarea, etc.)
- Définir les règles de validation
=================================================================
"""

from django import forms
from .models import Church, Event, Sermon, Member, Page, ContactMessage, SiteSettings


class ChurchForm(forms.ModelForm):
    """Formulaire de configuration d'une église."""
    class Meta:
        model = Church
        fields = [
            'name', 'description', 'logo', 'cover_image',
            'address', 'city', 'country', 'phone', 'email',
            'facebook', 'youtube', 'instagram',
            'primary_color', 'secondary_color',
            'welcome_message', 'service_times', 'pastor_name',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'welcome_message': forms.Textarea(attrs={'rows': 3}),
            'service_times': forms.Textarea(attrs={'rows': 3}),
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color'}),
        }


class EventForm(forms.ModelForm):
    """Formulaire de création/modification d'un événement."""
    class Meta:
        model = Event
        fields = ['title', 'description', 'image', 'event_date', 'event_time',
                  'end_date', 'location', 'is_featured', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'event_date': forms.DateInput(attrs={'type': 'date'}),
            'event_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class SermonForm(forms.ModelForm):
    """Formulaire de création/modification d'une prédication."""
    class Meta:
        model = Sermon
        fields = ['title', 'preacher', 'description', 'image', 'video_url',
                  'audio_url', 'sermon_date', 'bible_reference', 'is_featured', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'sermon_date': forms.DateInput(attrs={'type': 'date'}),
        }


class MemberForm(forms.ModelForm):
    """Formulaire d'ajout/modification d'un membre."""
    class Meta:
        model = Member
        fields = ['first_name', 'last_name', 'email', 'phone', 'address',
                  'birth_date', 'gender', 'membership_date', 'department', 'photo']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'membership_date': forms.DateInput(attrs={'type': 'date'}),
        }


class PageForm(forms.ModelForm):
    """Formulaire de création/modification d'une page."""
    class Meta:
        model = Page
        fields = ['title', 'content', 'image', 'sort_order', 'is_in_menu', 'is_active']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 10}),
        }


class ContactForm(forms.ModelForm):
    """Formulaire de contact public (visiteurs du site)."""
    class Meta:
        model = ContactMessage
        fields = ['sender_name', 'sender_email', 'subject', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),
        }


class SiteSettingsForm(forms.ModelForm):
    """Formulaire des paramètres globaux de la plateforme (super-admin)."""
    class Meta:
        model = SiteSettings
        fields = ['site_name', 'site_slogan', 'site_description', 'site_logo', 'cover_image', 'contact_email']
        widgets = {
            'site_description': forms.Textarea(attrs={'rows': 3}),
        }
