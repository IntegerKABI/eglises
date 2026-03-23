"""Form classes for church domain validation and UI binding."""

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
from .limits import enforce_limits_for_model
from .membership_policy import validate_single_church_membership


PLAN_OVERRIDE_FIELDS = [
    'max_members_override',
    'max_events_override',
    'max_sermons_override',
    'max_pages_override',
    'max_users_override',
    'max_pending_invitations_override',
    'max_storage_mb_override',
    'message_retention_days_override',
    'notification_retention_days_override',
]


class ChurchForm(forms.ModelForm):
    """Edit the tenant-facing church profile settings."""
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
    """Create or update an event."""
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
    """Create or update a sermon."""
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
    """Create or update a member record."""
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
    """Create or update a custom page."""
    class Meta:
        model = Page
        fields = ['title', 'content', 'image', 'sort_order', 'is_in_menu',
                  'visibility', 'published_at', 'is_active']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 10}),
            'published_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class ContactForm(forms.ModelForm):
    """Validate public contact form submissions."""
    class Meta:
        model = ContactMessage
        fields = ['sender_name', 'sender_email', 'subject', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),
        }


class SiteSettingsForm(forms.ModelForm):
    """Edit global platform settings."""
    class Meta:
        model = SiteSettings
        fields = ['site_name', 'site_slogan', 'site_description', 'site_logo', 'cover_image', 'contact_email']
        widgets = {
            'site_description': forms.Textarea(attrs={'rows': 3}),
        }


class SuperAdminChurchUpdateForm(forms.ModelForm):
    """Update tenant profile fields without touching plan or lifecycle state."""

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


class SuperAdminChurchPlanForm(forms.ModelForm):
    """Update the SaaS plan and override limits for a tenant."""

    class Meta:
        model = Church
        fields = ['plan', *PLAN_OVERRIDE_FIELDS]
        widgets = {
            field_name: forms.NumberInput(attrs={'min': 0})
            for field_name in PLAN_OVERRIDE_FIELDS
        }


class SuperAdminChurchStatusForm(forms.ModelForm):
    """Validate tenant lifecycle state transitions."""

    class Meta:
        model = Church
        fields = ['status']


class SuperAdminChurchCreateForm(forms.ModelForm):
    """Create a tenant and either invite or attach its first administrator."""

    admin_assignment_mode = forms.ChoiceField(
        label="Mode d'attribution de l'administrateur",
        choices=[
            ('existing', "Inviter un utilisateur existant"),
            ('new', "Creer et rattacher un nouvel utilisateur"),
        ],
        initial='existing',
    )
    existing_admin_identifier = forms.CharField(
        label="Utilisateur existant (email ou nom d'utilisateur)",
        required=False,
        max_length=150,
    )
    new_admin_username = forms.CharField(
        label="Nom d'utilisateur du nouvel administrateur",
        required=False,
        max_length=150,
    )
    new_admin_email = forms.EmailField(
        label="Email du nouvel administrateur",
        required=False,
    )
    new_admin_first_name = forms.CharField(
        label="Prenom du nouvel administrateur",
        required=False,
        max_length=150,
    )
    new_admin_last_name = forms.CharField(
        label="Nom du nouvel administrateur",
        required=False,
        max_length=150,
    )
    new_admin_password1 = forms.CharField(
        label="Mot de passe",
        required=False,
        widget=forms.PasswordInput,
    )
    new_admin_password2 = forms.CharField(
        label="Confirmer le mot de passe",
        required=False,
        widget=forms.PasswordInput,
    )

    class Meta:
        model = Church
        fields = [
            'name', 'description', 'logo', 'cover_image',
            'address', 'city', 'country', 'phone', 'email',
            'facebook', 'youtube', 'instagram',
            'primary_color', 'secondary_color',
            'welcome_message', 'service_times', 'pastor_name',
            'status', 'plan', *PLAN_OVERRIDE_FIELDS,
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'welcome_message': forms.Textarea(attrs={'rows': 3}),
            'service_times': forms.Textarea(attrs={'rows': 3}),
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color'}),
            **{
                field_name: forms.NumberInput(attrs={'min': 0})
                for field_name in PLAN_OVERRIDE_FIELDS
            },
        }

    def __init__(self, *args, **kwargs):
        self.admin_user = None
        self.create_new_admin = False
        super().__init__(*args, **kwargs)
        self.fields['status'].initial = Church.Status.DRAFT
        for field_name in ('country', 'primary_color', 'secondary_color'):
            self.fields[field_name].required = False
            self.fields[field_name].initial = self._meta.model._meta.get_field(field_name).default

    def clean(self):
        cleaned_data = super().clean()
        for field_name in ('country', 'primary_color', 'secondary_color'):
            if not cleaned_data.get(field_name):
                cleaned_data[field_name] = self._meta.model._meta.get_field(field_name).default

        mode = cleaned_data.get('admin_assignment_mode')
        if mode == 'existing':
            self._clean_existing_admin(cleaned_data)
            if cleaned_data.get('status') == Church.Status.ACTIVE:
                self.add_error(
                    'status',
                    "Une eglise active doit etre creee avec un administrateur immediat. Utilisez le mode de creation de compte ou creez l'eglise en brouillon.",
                )
        elif mode == 'new':
            self._clean_new_admin(cleaned_data)
            if cleaned_data.get('status') == Church.Status.ACTIVE and self.admin_user is None:
                self.add_error(
                    'status',
                    "Une eglise active doit etre creee avec un administrateur actif.",
                )
        else:
            self.add_error('admin_assignment_mode', "Mode d'attribution invalide.")

        return cleaned_data

    def _clean_existing_admin(self, cleaned_data):
        identifier = (cleaned_data.get('existing_admin_identifier') or '').strip()
        if not identifier:
            self.add_error(
                'existing_admin_identifier',
                "Renseignez l'identifiant de l'utilisateur existant.",
            )
            return

        User = get_user_model()
        user = User.objects.filter(username=identifier).first()
        if user is None:
            user = User.objects.filter(email__iexact=identifier).first()
        if user is None:
            self.add_error(
                'existing_admin_identifier',
                "Aucun utilisateur n'a ete trouve avec cet identifiant.",
            )
            return
        if user.is_superuser:
            self.add_error(
                'existing_admin_identifier',
                "Un superadministrateur ne peut pas etre assigne comme admin de tenant.",
            )
            return
        if not user.is_active:
            self.add_error(
                'existing_admin_identifier',
                "L'utilisateur selectionne doit etre actif.",
            )
            return
        if not (user.email or '').strip():
            self.add_error(
                'existing_admin_identifier',
                "L'utilisateur selectionne doit avoir un email pour recevoir l'invitation.",
            )
            return
        try:
            validate_single_church_membership(user)
        except ValidationError as exc:
            self.add_error('existing_admin_identifier', exc.messages[0])
            return

        self.admin_user = user
        self.create_new_admin = False

    def _clean_new_admin(self, cleaned_data):
        required_fields = {
            'new_admin_username': "Le nom d'utilisateur est obligatoire.",
            'new_admin_email': "L'email est obligatoire.",
            'new_admin_password1': "Le mot de passe est obligatoire.",
            'new_admin_password2': "La confirmation du mot de passe est obligatoire.",
        }
        for field_name, message in required_fields.items():
            if not cleaned_data.get(field_name):
                self.add_error(field_name, message)

        if any(field in self.errors for field in required_fields):
            return

        password1 = cleaned_data.get('new_admin_password1')
        password2 = cleaned_data.get('new_admin_password2')
        if password1 != password2:
            self.add_error('new_admin_password2', "Les mots de passe ne correspondent pas.")
            return

        User = get_user_model()
        username = cleaned_data['new_admin_username']
        email = cleaned_data['new_admin_email'].strip().lower()
        if User.objects.filter(username=username).exists():
            self.add_error('new_admin_username', "Ce nom d'utilisateur est deja utilise.")
        if User.objects.filter(email__iexact=email).exists():
            self.add_error('new_admin_email', "Un compte existe deja avec cet email.")
        if any(field in self.errors for field in ('new_admin_username', 'new_admin_email')):
            return

        provisional_user = User(
            username=username,
            email=email,
            first_name=cleaned_data.get('new_admin_first_name', ''),
            last_name=cleaned_data.get('new_admin_last_name', ''),
            is_active=True,
        )
        try:
            validate_password(password1, provisional_user)
        except ValidationError as exc:
            self.add_error('new_admin_password1', exc)
            return

        self.admin_user = provisional_user
        self.create_new_admin = True

    def save(self, commit=True, invited_by=None):
        if not commit:
            raise ValueError("SuperAdminChurchCreateForm.save requires commit=True.")
        if self.admin_user is None:
            raise ValueError("Le formulaire doit etre valide avant l'enregistrement.")

        with transaction.atomic():
            church = super().save(commit=True)
            admin_user = self.admin_user
            membership = None
            invitation = None
            if self.create_new_admin:
                enforce_limits_for_model(church, ChurchMembership)
                admin_user.set_password(self.cleaned_data['new_admin_password1'])
                admin_user.is_active = True
                admin_user.save()
                membership = ChurchMembership.objects.create(
                    user=admin_user,
                    church=church,
                    role=ChurchMembership.Role.ADMIN,
                    is_active=True,
                )
            else:
                enforce_limits_for_model(church, ChurchInvitation)
                invitation = ChurchInvitation.objects.create(
                    church=church,
                    email=admin_user.email.strip().lower(),
                    role=ChurchMembership.Role.ADMIN,
                    invited_by=invited_by,
                )

        self.created_admin_user = admin_user
        self.created_membership = membership
        self.created_invitation = invitation
        return church


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
        if password1:
            provisional_user = self.instance or get_user_model()()
            provisional_user.username = cleaned_data.get('username')
            provisional_user.email = cleaned_data.get('email')
            provisional_user.first_name = cleaned_data.get('first_name')
            provisional_user.last_name = cleaned_data.get('last_name')
            try:
                validate_password(password1, provisional_user)
            except ValidationError as exc:
                self.add_error('password1', exc)
        return cleaned_data

    def save(self, church, commit=True):
        if not commit:
            raise ValueError("ChurchUserCreateForm.save requires commit=True.")

        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        with transaction.atomic():
            enforce_limits_for_model(church, ChurchMembership)
            user.save()
            self.membership = ChurchMembership.objects.create(
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

        with transaction.atomic():
            membership = (
                ChurchMembership.objects.select_for_update()
                .filter(user=self.user, church=church)
                .first()
            )
            if membership:
                if not membership.is_active:
                    enforce_limits_for_model(church, ChurchMembership)
                membership.role = self.cleaned_data['role']
                membership.is_active = True
                membership.save(update_fields=['role', 'is_active'])
                self.created = False
                self.membership = membership
                return membership

            self.created = True
            enforce_limits_for_model(church, ChurchMembership)
            self.membership = ChurchMembership.objects.create(
                user=self.user,
                church=church,
                role=self.cleaned_data['role'],
                is_active=True,
            )
            return self.membership


class ChurchMembershipUpdateForm(forms.ModelForm):
    class Meta:
        model = ChurchMembership
        fields = ['role', 'is_active']


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
            if ChurchInvitation.objects.actionable().filter(
                church=self.church,
                email__iexact=email,
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
            if self.church and invite.status == ChurchInvitation.Status.PENDING:
                enforce_limits_for_model(self.church, ChurchInvitation)
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



