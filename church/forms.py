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
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    Church,
    ChurchInvitation,
    ChurchMembership,
    Event,
    Sermon,
    Member,
    Page,
    ContactMessage,
    ContactMessageReply,
    SiteSettings,
)
from .membership_policy import validate_single_church_membership


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
                  'end_date', 'location', 'visibility', 'published_at', 'is_featured', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'event_date': forms.DateInput(attrs={'type': 'date'}),
            'event_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'published_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
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
                  'audio_url', 'sermon_date', 'bible_reference', 'visibility', 'published_at',
                  'is_featured', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'sermon_date': forms.DateInput(attrs={'type': 'date'}),
            'published_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class MemberForm(forms.ModelForm):
    """Formulaire d'ajout/modification d'un membre."""
    class Meta:
        model = Member
        fields = ['first_name', 'last_name', 'email', 'phone', 'address',
                  'birth_date', 'gender', 'membership_date', 'department',
                  'directory_consent', 'directory_consent_source', 'photo']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'membership_date': forms.DateInput(attrs={'type': 'date'}),
            'directory_consent_source': forms.TextInput(attrs={'placeholder': 'Formulaire papier, email, oral...'}),
        }


class PageForm(forms.ModelForm):
    """Formulaire de création/modification d'une page."""
    class Meta:
        model = Page
        fields = ['title', 'content', 'image', 'sort_order', 'is_in_menu',
                  'visibility', 'published_at', 'is_active']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 10}),
            'published_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
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


class ContactMessageReplyForm(forms.ModelForm):
    class Meta:
        model = ContactMessageReply
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
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
        if not commit:
            raise ValueError("ChurchUserCreateForm.save requires commit=True.")

        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        with transaction.atomic():
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
        if self.church:
            validate_single_church_membership(user, church=self.church)
            existing = ChurchMembership.objects.filter(user=user, church=self.church).first()
            if existing and existing.is_active:
                raise ValidationError("Cet utilisateur est déjà membre actif de cette église.")
        self.user = user
        return cleaned_data

    def save(self, church):
        if not self.user:
            raise ValidationError("Utilisateur introuvable.")
        membership = ChurchMembership.objects.filter(user=self.user, church=church).first()
        if membership:
            membership.role = self.cleaned_data['role']
            membership.is_active = True
            membership.save(update_fields=['role', 'is_active'])
            self.created = False
            return membership
        self.created = True
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

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance or not self.instance.pk:
            return cleaned_data
        new_role = cleaned_data.get('role')
        new_active = cleaned_data.get('is_active')
        if (
            self.instance.role == ChurchMembership.Role.ADMIN
            and (new_role != ChurchMembership.Role.ADMIN or not new_active)
        ):
            other_admins = ChurchMembership.objects.filter(
                church=self.instance.church,
                role=ChurchMembership.Role.ADMIN,
                is_active=True,
            ).exclude(pk=self.instance.pk)
            if not other_admins.exists():
                raise ValidationError("Au moins un administrateur actif est requis.")
        if new_active:
            validate_single_church_membership(
                self.instance.user,
                church=self.instance.church,
            )
        return cleaned_data


class ChurchInvitationForm(forms.ModelForm):
    class Meta:
        model = ChurchInvitation
        fields = ['email', 'role']

    def __init__(self, *args, church=None, invited_by=None, **kwargs):
        self.church = church
        self.invited_by = invited_by
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            return email
        if self.church:
            User = get_user_model()
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user:
                validate_single_church_membership(existing_user, church=self.church)
            if ChurchMembership.objects.filter(church=self.church, user__email__iexact=email, is_active=True).exists():
                raise ValidationError("Cet utilisateur est déjà membre actif de cette église.")
            if ChurchInvitation.objects.filter(
                church=self.church,
                email__iexact=email,
                status=ChurchInvitation.Status.PENDING,
            ).exists():
                raise ValidationError("Une invitation en attente existe déjà pour cet email.")
        return email

    def save(self, commit=True):
        invite = super().save(commit=False)
        if self.church:
            invite.church = self.church
        if self.invited_by:
            invite.invited_by = self.invited_by
        if commit:
            invite.save()
        return invite


class TransferAdminForm(forms.Form):
    membership = forms.ModelChoiceField(
        queryset=ChurchMembership.objects.none(),
        label="Nouvel administrateur",
    )

    def __init__(self, *args, church=None, current_membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = ChurchMembership.objects.filter(church=church, is_active=True)
        if current_membership:
            queryset = queryset.exclude(pk=current_membership.pk)
        self.fields['membership'].queryset = queryset.select_related('user')


class InviteSignupForm(forms.ModelForm):
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput)

    class Meta:
        model = get_user_model()
        fields = ['username', 'first_name', 'last_name']

    def __init__(self, *args, email=None, **kwargs):
        self.invite_email = (email or '').strip().lower()
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            return username
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise ValidationError("Ce nom d'utilisateur est déjà utilisé.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Les mots de passe ne correspondent pas.")
        if password1:
            try:
                validate_password(password1, self.instance)
            except ValidationError as exc:
                self.add_error('password1', exc)
        User = get_user_model()
        if self.invite_email and User.objects.filter(email__iexact=self.invite_email).exists():
            raise ValidationError("Un compte existe déjà avec cet email. Connectez-vous.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.invite_email
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user
