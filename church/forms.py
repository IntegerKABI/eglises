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
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Church, ChurchMembership, Event, Sermon, Member, Page, ContactMessage, SiteSettings


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

    def clean(self):
        cleaned_data = super().clean()
        event_date = cleaned_data.get("event_date")
        end_date = cleaned_data.get("end_date")
        if event_date and end_date and end_date < event_date:
            self.add_error(
                "end_date",
                "La date de fin doit etre posterieure ou egale a la date de l'evenement.",
            )
        return cleaned_data


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


class ChurchUserCreateForm(forms.ModelForm):
    role = forms.ChoiceField(choices=ChurchMembership.Role.choices)
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput)

    class Meta:
        model = get_user_model()
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'is_active']

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError("Les mots de passe ne correspondent pas.")
        return cleaned_data

    def save(self, church, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        ChurchMembership.objects.create(
            user=user,
            church=church,
            role=self.cleaned_data['role'],
            is_active=True,
        )
        return user


class ChurchMembershipAssignForm(forms.Form):
    identifier = forms.CharField(
        label="Utilisateur (email ou nom d'utilisateur)",
        max_length=150,
    )
    role = forms.ChoiceField(choices=ChurchMembership.Role.choices)

    def __init__(self, *args, church=None, **kwargs):
        self.user = None
        self.church = church
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        identifier = cleaned_data.get('identifier')
        if not identifier:
            return cleaned_data
        User = get_user_model()
        user = User.objects.filter(username=identifier).first()
        if not user:
            user = User.objects.filter(email__iexact=identifier).first()
        if not user:
            raise ValidationError("Aucun utilisateur trouvé avec cet identifiant.")
        if self.church and ChurchMembership.objects.filter(user=user, church=self.church).exists():
            raise ValidationError("Cet utilisateur est déjà membre de cette église.")
        self.user = user
        return cleaned_data

    def save(self, church):
        if not self.user:
            raise ValidationError("Utilisateur introuvable.")
        return ChurchMembership.objects.create(
            user=self.user,
            church=church,
            role=self.cleaned_data['role'],
            is_active=True,
        )


class ChurchMembershipUpdateForm(forms.ModelForm):
    class Meta:
        model = ChurchMembership
        fields = ['role', 'is_active']
