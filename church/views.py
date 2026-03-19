"""
=================================================================
VUES — Logique de chaque page
=================================================================
Chaque fonction ici correspond à une page du site.

COMMENT ÇA MARCHE :
1. L'utilisateur tape une URL (ex: /eglise/demo/)
2. Django cherche quelle vue correspond à cette URL (dans urls.py)
3. La vue récupère les données depuis la base de données
4. La vue envoie ces données à un template HTML
5. Le template génère la page HTML finale

Il y a 2 sections :
- VUES PUBLIQUES : ce que les visiteurs voient
- VUES DASHBOARD : l'interface d'administration pour le pasteur
=================================================================
"""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .models import (
    Church,
    ChurchInvitation,
    ChurchMembership,
    Event,
    Sermon,
    Member,
    Page,
    ContactMessage,
    SiteSettings,
    filter_public_queryset,
    Notification,
    AuditLog,
)
from .forms import (
    ChurchForm,
    EventForm,
    SermonForm,
    MemberForm,
    PageForm,
    ContactForm,
    ContactMessageReplyForm,
    ChurchUserCreateForm,
    ChurchMembershipAssignForm,
    ChurchMembershipUpdateForm,
    ChurchInvitationForm,
    InviteSignupForm,
    TransferAdminForm,
    SiteSettingsForm,
)
from .permissions import (
    CAP_MANAGE_CHURCH_SETTINGS,
    CAP_MANAGE_EVENTS,
    CAP_MANAGE_MEMBERS,
    CAP_MANAGE_MESSAGES,
    CAP_MANAGE_PAGES,
    CAP_MANAGE_SERMONS,
    CAP_MANAGE_SITE_SETTINGS,
    CAP_MANAGE_USERS,
    CAP_VIEW_AUDIT,
    CAP_VIEW_DASHBOARD,
    get_churches_for_capability,
    require_capability,
)
from .notifications import (
    notify_church_admins,
    notify_message_recipients,
    notify_event_recipients,
    notify_user,
    notify_user_role_change,
)
from .audit import log_audit
from .limits import (
    enforce_limits_for_model,
    filter_messages_for_retention,
    filter_notifications_for_retention,
    get_plan_usage,
)
from .membership_policy import (
    get_pending_invitations_for_user,
    validate_single_church_membership,
)
from .tenancy import get_accessible_churches, get_membership, get_selected_church


class TenantLoginView(LoginView):
    template_name = "registration/login.html"

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to

        user = self.request.user
        churches = get_accessible_churches(user)
        church_count = churches.count()

        if church_count == 0:
            self.request.session.pop("active_church_id", None)
            if _has_pending_invitations(user):
                return reverse("pending_invitations")
            logout(self.request)
            messages.error(
                self.request,
                "Votre compte n'appartient a aucune eglise active et vous n'avez aucune invitation en attente. Contactez l'administration de l'eglise ou la plateforme.",
            )
            return reverse("home")

        if not user.is_superuser and church_count > 1:
            self.request.session.pop("active_church_id", None)
            logout(self.request)
            messages.error(
                self.request,
                "Votre compte est associe a plusieurs eglises actives. Contactez le superadministrateur.",
            )
            return reverse("home")

        active_church_id = self.request.session.get("active_church_id")
        if active_church_id and churches.filter(id=active_church_id).exists():
            return reverse("dashboard")

        if church_count == 1:
            self.request.session["active_church_id"] = churches.values_list("id", flat=True).first()
            return reverse("dashboard")

        self.request.session.pop("active_church_id", None)
        return reverse("select_church")


def is_ajax(request):
    """Vérifie si la requête est AJAX."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _querystring_without_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


def _parse_bool_param(value):
    if value in ('1', 'true', 'yes', 'on'):
        return True
    if value in ('0', 'false', 'no', 'off'):
        return False
    return None


def _get_text_param(request, key, max_len=200):
    value = request.GET.get(key, '')
    if value is None:
        return ''
    value = value.strip()
    if len(value) > max_len:
        value = value[:max_len]
    return value


def _get_choice_param(request, key, allowed):
    value = request.GET.get(key)
    return value if value in allowed else ''


def _has_other_admins(church, exclude_membership=None):
    admins = ChurchMembership.objects.filter(
        church=church,
        role=ChurchMembership.Role.ADMIN,
        is_active=True,
    )
    if exclude_membership:
        admins = admins.exclude(pk=exclude_membership.pk)
    return admins.exists()


def _build_invite_url(request, invite):
    return request.build_absolute_uri(reverse('accept_invite', args=[invite.token]))


def _send_invite_email(request, invite):
    invite_url = _build_invite_url(request, invite)
    subject = f"Invitation à rejoindre {invite.church.name}"
    message = (
        f"Bonjour,\n\n"
        f"Vous avez été invité à rejoindre {invite.church.name} en tant que {invite.get_role_display()}.\n"
        f"Pour accepter l'invitation, cliquez ici : {invite_url}\n\n"
        f"Cette invitation expirera le {invite.expires_at:%d/%m/%Y %H:%M}.\n"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
        [invite.email],
        fail_silently=False,
    )


def _mark_invite_notifications_read(user, invite):
    Notification.objects.filter(
        recipient=user,
        church=invite.church,
        category=Notification.Category.INVITE,
        is_read=False,
    ).filter(
        Q(link__icontains=str(invite.token)) | Q(title__icontains="Invitation")
    ).update(is_read=True)


def _has_pending_invitations(user):
    return get_pending_invitations_for_user(user).exists()


def _schedule_safe_after_commit(callback):
    def wrapped():
        try:
            callback()
        except Exception:
            pass

    transaction.on_commit(wrapped)


def _require_church(request):
    church = getattr(request, 'current_church', None)
    if church is None:
        church = get_selected_church(request, prefetch_pages=True)
        request.current_church = church
    if not church:
        messages.warning(request, "Sélectionnez une église pour continuer.")
        return None
    if request.user.is_authenticated and not request.user.is_superuser:
        membership = getattr(request, 'current_membership', None)
        if membership is None:
            membership = get_membership(request.user, church)
            request.current_membership = membership
        if not membership:
            messages.error(request, "Accès refusé. Aucun rôle défini pour cette église.")
            return None
        if church.status in {Church.Status.SUSPENDED, Church.Status.ARCHIVED}:
            messages.error(request, "Cette église est suspendue ou archivée.")
            request.session.pop('active_church_id', None)
            return None
    return church


def _get_public_church(request, church_slug):
    church = getattr(request, 'current_church', None)
    current_slug = getattr(request, 'current_church_slug', None)
    if current_slug == church_slug:
        if church is None:
            raise Http404("Église introuvable.")
        return church
    return get_object_or_404(Church, slug=church_slug, status=Church.Status.ACTIVE)


def _handle_church_form(
    request,
    form_class,
    template_name,
    success_message,
    success_url_name,
    title,
    *,
    instance=None,
    object_name=None,
    model=None,
    pk=None,
    after_save=None,
):
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    if instance is None and model is not None and pk is not None:
        instance = get_object_or_404(model, pk=pk, church=church)

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            if hasattr(obj, 'church_id'):
                obj.church = church
            if obj.pk is None and getattr(obj, 'created_by_id', None) is None and request.user.is_authenticated:
                obj.created_by = request.user
            is_created = obj.pk is None
            try:
                enforce_limits_for_model(
                    church,
                    obj.__class__,
                    instance=instance or obj,
                    form=form,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
                context = {
                    'church': church,
                    'form': form,
                    'title': title,
                }
                if object_name and instance is not None:
                    context[object_name] = instance
                if is_ajax(request):
                    return JsonResponse({'success': False, 'errors': form.errors}, status=400)
                return render(request, template_name, context)
            obj.save()
            if hasattr(form, 'save_m2m'):
                form.save_m2m()
            try:
                action = "create" if is_created else "update"
                log_audit(
                    actor=request.user,
                    church=church if hasattr(obj, 'church_id') else None,
                    action=action,
                    instance=obj,
                    metadata={"form": form.__class__.__name__},
                )
            except Exception:
                pass
            if after_save:
                after_save(obj, is_created)
            if is_ajax(request):
                return JsonResponse({
                    'success': True,
                    'message': success_message,
                    'redirect': reverse(success_url_name),
                })
            messages.success(request, success_message)
            return redirect(success_url_name)
        if is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = form_class(instance=instance)

    context = {
        'church': church,
        'form': form,
        'title': title,
    }
    if object_name and instance is not None:
        context[object_name] = instance
    return render(request, template_name, context)


def _handle_church_delete(request, model, pk, success_message, success_url_name, *, after_delete=None):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    obj = get_object_or_404(model, pk=pk, church=church)
    if request.method == 'POST':
        if after_delete:
            after_delete(obj)
        try:
            log_audit(
                actor=request.user,
                church=church,
                action="delete",
                instance=obj,
            )
        except Exception:
            pass
        obj.delete()
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': success_message})
        messages.success(request, success_message)
    return redirect(success_url_name)


# =============================================================
#  VUES PUBLIQUES — Site visible par tous
# =============================================================

def home(request):
    """Page d'accueil — liste toutes les églises disponibles."""
    churches = Church.objects.filter(status=Church.Status.ACTIVE)
    q = _get_text_param(request, 'q', 100)
    if q:
        churches = churches.filter(
            Q(name__icontains=q) |
            Q(city__icontains=q) |
            Q(country__icontains=q)
        )
    paginator = Paginator(churches, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'church/home.html', {
        'churches': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


def church_home(request, church_slug):
    """
    Page d'accueil d'une église spécifique.
    Ex: /eglise/demo/ → affiche l'église avec le slug "demo"
    """
    church = _get_public_church(request, church_slug)
    upcoming_events = filter_public_queryset(church.events).filter(
        event_date__gte=timezone.now().date()
    )[:3]
    latest_sermons = filter_public_queryset(church.sermons)[:3]
    custom_pages = filter_public_queryset(church.pages).filter(is_in_menu=True)

    return render(request, 'church/church_home.html', {
        'church': church,
        'upcoming_events': upcoming_events,
        'latest_sermons': latest_sermons,
        'custom_pages': custom_pages,
    })


def church_events(request, church_slug):
    """Liste de tous les événements d'une église."""
    church = _get_public_church(request, church_slug)
    events = filter_public_queryset(church.events)
    q = _get_text_param(request, 'q', 100)
    if q:
        events = events.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(location__icontains=q)
        )
    featured = _parse_bool_param(request.GET.get('featured'))
    if featured is True:
        events = events.filter(is_featured=True)
    elif featured is False:
        events = events.filter(is_featured=False)
    when = _get_choice_param(request, 'when', {'upcoming', 'past'})
    today = timezone.now().date()
    if when == 'upcoming':
        events = events.filter(event_date__gte=today)
    elif when == 'past':
        events = events.filter(event_date__lt=today)
    paginator = Paginator(events, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'church/events.html', {
        'church': church,
        'events': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


def church_sermons(request, church_slug):
    """Liste de toutes les prédications d'une église."""
    church = _get_public_church(request, church_slug)
    sermons = filter_public_queryset(church.sermons)
    q = _get_text_param(request, 'q', 100)
    if q:
        sermons = sermons.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(preacher__icontains=q) |
            Q(bible_reference__icontains=q)
        )
    featured = _parse_bool_param(request.GET.get('featured'))
    if featured is True:
        sermons = sermons.filter(is_featured=True)
    elif featured is False:
        sermons = sermons.filter(is_featured=False)
    paginator = Paginator(sermons, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'church/sermons.html', {
        'church': church,
        'sermons': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


def church_page(request, church_slug, page_slug):
    """Affiche une page dynamique personnalisée."""
    church = _get_public_church(request, church_slug)
    page = get_object_or_404(filter_public_queryset(Page.objects.filter(church=church, slug=page_slug)))
    return render(request, 'church/custom_page.html', {
        'church': church,
        'page': page,
    })


def church_contact(request, church_slug):
    """Formulaire de contact d'une église."""
    church = _get_public_church(request, church_slug)

    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.church = church
            message.save()
            notify_message_recipients(
                church,
                category="message",
                title="Nouveau message reçu",
                body=f"{message.sender_name} - {message.subject or 'Sans sujet'}",
                link=reverse('read_message', args=[message.pk]),
            )
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Votre message a été envoyé avec succès !'})
            messages.success(request, 'Votre message a été envoyé avec succès !')
            return redirect('church_contact', church_slug=church_slug)
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = ContactForm()

    return render(request, 'church/contact.html', {
        'church': church,
        'form': form,
    })


def accept_invite(request, token):
    invite = get_object_or_404(ChurchInvitation, token=token)
    if invite.status != ChurchInvitation.Status.PENDING:
        messages.info(request, "Cette invitation n'est plus disponible.")
        if request.user.is_authenticated:
            return redirect('pending_invitations')
        return redirect('home')
    if invite.church.status in {Church.Status.SUSPENDED, Church.Status.ARCHIVED}:
        messages.error(request, "Cette église n'accepte pas de nouvelles invitations.")
        if request.user.is_authenticated:
            return redirect('pending_invitations')
        return redirect('home')
    if invite.is_expired:
        invite.status = ChurchInvitation.Status.EXPIRED
        invite.save(update_fields=['status'])
        messages.error(request, "Cette invitation a expiré.")
        if request.user.is_authenticated:
            return redirect('pending_invitations')
        return redirect('home')

    if not request.user.is_authenticated:
        form = InviteSignupForm(request.POST or None, email=invite.email)
        if request.method == 'POST' and form.is_valid():
            user = form.save()
            login(request, user)
            request.user = user
        else:
            return render(request, 'church/accept_invite_signup.html', {
                'invite': invite,
                'church': invite.church,
                'form': form,
            })

    user_email = (request.user.email or '').strip().lower()
    if not user_email or user_email != invite.email.lower():
        messages.error(request, "Cette invitation ne correspond pas à votre email.")
        return redirect('dashboard')

    try:
        validate_single_church_membership(request.user, church=invite.church)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect('pending_invitations')

    if request.method == 'POST':
        with transaction.atomic():
            membership = (
                ChurchMembership.objects.select_for_update()
                .filter(user=request.user, church=invite.church)
                .first()
            )
            if membership:
                new_role = invite.role
                if membership.role == ChurchMembership.Role.ADMIN and invite.role != ChurchMembership.Role.ADMIN:
                    new_role = membership.role
                if membership.role != new_role:
                    membership.role = new_role
                if not membership.is_active:
                    enforce_limits_for_model(invite.church, ChurchMembership)
                membership.is_active = True
                membership.save(update_fields=['role', 'is_active'])
            else:
                enforce_limits_for_model(invite.church, ChurchMembership)
                ChurchMembership.objects.create(
                    user=request.user,
                    church=invite.church,
                    role=invite.role,
                    is_active=True,
                )
            invite.status = ChurchInvitation.Status.ACCEPTED
            invite.accepted_at = timezone.now()
            invite.accepted_by = request.user
            invite.save(update_fields=['status', 'accepted_at', 'accepted_by'])
        try:
            log_audit(
                actor=request.user,
                church=invite.church,
                action="invite_accept",
                instance=invite,
                metadata={"email": invite.email, "role": invite.role},
            )
        except Exception:
            pass
        notify_church_admins(
            invite.church,
            category="invite",
            title="Invitation acceptée",
            body=f"{request.user.get_full_name() or request.user.username} a rejoint l'église.",
            link=reverse('manage_users'),
            exclude=request.user,
        )
        if invite.invited_by and invite.invited_by != request.user:
            notify_user(
                invite.invited_by,
                invite.church,
                category="invite",
                title="Invitation acceptée",
                body=f"{request.user.get_full_name() or request.user.username} a accepté l'invitation.",
                link=reverse('manage_users'),
            )
        _mark_invite_notifications_read(request.user, invite)
        messages.success(request, "Invitation acceptée. Bienvenue !")
        return redirect('dashboard')

    return render(request, 'church/accept_invite.html', {
        'invite': invite,
        'church': invite.church,
    })


@login_required
def pending_invitations(request):
    invitations = get_pending_invitations_for_user(request.user)
    if invitations.exists():
        return render(request, 'church/pending_invitations.html', {
            'invitations': invitations,
        })

    churches = get_accessible_churches(request.user)
    if churches.exists():
        return redirect('dashboard')

    logout(request)
    messages.info(
        request,
        "Votre compte n'appartient a aucune eglise active et vous n'avez aucune invitation en attente. Contactez l'administration de l'eglise ou la plateforme.",
    )
    return redirect('home')

@login_required
def decline_invite(request, token):
    invite = get_object_or_404(
        ChurchInvitation,
        token=token,
        status=ChurchInvitation.Status.PENDING,
        email__iexact=request.user.email,
    )
    if request.method != 'POST':
        return redirect('pending_invitations')
    if invite.is_expired:
        invite.status = ChurchInvitation.Status.EXPIRED
        invite.save(update_fields=['status'])
        messages.error(request, "Cette invitation a expire.")
        return redirect('pending_invitations')

    invite.status = ChurchInvitation.Status.DECLINED
    invite.declined_at = timezone.now()
    invite.save(update_fields=['status', 'declined_at'])
    _mark_invite_notifications_read(request.user, invite)
    try:
        log_audit(
            actor=request.user,
            church=invite.church,
            action="invite_decline",
            instance=invite,
            metadata={"email": invite.email, "role": invite.role},
        )
    except Exception:
        pass
    notify_church_admins(
        invite.church,
        category="invite",
        title="Invitation refusee",
        body=f"{request.user.get_full_name() or request.user.username} a refuse l'invitation.",
        link=reverse('manage_users'),
        exclude=request.user,
    )
    if invite.invited_by and invite.invited_by != request.user:
        notify_user(
            invite.invited_by,
            invite.church,
            category="invite",
            title="Invitation refusee",
            body=f"{request.user.get_full_name() or request.user.username} a refuse l'invitation.",
            link=reverse('manage_users'),
        )
    if _has_pending_invitations(request.user) or get_accessible_churches(request.user).exists():
        messages.success(request, "Invitation refusee.")
        return redirect('pending_invitations')

    logout(request)
    messages.success(request, "Invitation refusee. Vous avez ete deconnecte car votre compte n'a plus aucun acces actif.")
    return redirect('home')


@login_required
def select_church(request):
    churches = get_accessible_churches(request.user)
    if not churches.exists():
        messages.warning(request, "Aucune église associée à votre compte.")
        return redirect('home')

    if not request.user.is_superuser:
        if churches.count() > 1:
            request.session.pop('active_church_id', None)
            messages.error(
                request,
                "Votre compte est associe a plusieurs eglises actives. Contactez le superadministrateur.",
            )
            return redirect('home')
        church = churches.first()
        request.session['active_church_id'] = church.id
        return redirect('dashboard')

    if request.method == 'POST':
        church_id = request.POST.get('church_id')
        church = churches.filter(id=church_id).first()
        if not church:
            messages.error(request, "Sélection d'église invalide.")
        else:
            request.session['active_church_id'] = church.id
            return redirect('dashboard')

    return render(request, 'admin_dashboard/select_church.html', {
        'churches': churches,
        'selected_church_id': request.session.get('active_church_id'),
    })


# =============================================================
#  VUES DASHBOARD — Interface d'administration (pasteur/admin)
# =============================================================

@login_required
@require_capability(CAP_VIEW_DASHBOARD)
def dashboard(request):
    """
    Tableau de bord principal.
    Affiche les statistiques de l'église de l'utilisateur connecté.
    """
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    recent_messages = filter_messages_for_retention(
        church.messages.filter(status=ContactMessage.Status.NEW),
        church,
    )

    context = {
        'church': church,
        'total_members': church.members.filter(is_active=True).count(),
        'total_events': church.events.filter(is_active=True).count(),
        'total_sermons': church.sermons.filter(is_active=True).count(),
        'plan_usage': get_plan_usage(church),
        'plan_member_limit': church.get_plan_limit('members'),
        'plan_event_limit': church.get_plan_limit('events'),
        'plan_sermon_limit': church.get_plan_limit('sermons'),
        'plan_page_limit': church.get_plan_limit('pages'),
        'plan_user_limit': church.get_plan_limit('users'),
        'plan_pending_invitation_limit': church.get_plan_limit('pending_invitations'),
        'plan_storage_limit_mb': church.get_plan_limit('storage_mb'),
        'plan_message_retention_days': church.get_plan_limit('message_retention_days'),
        'plan_notification_retention_days': church.get_plan_limit('notification_retention_days'),
        'plan_member_limit_display': church.get_plan_limit('members') if church.get_plan_limit('members') is not None else 'Illimite',
        'plan_event_limit_display': church.get_plan_limit('events') if church.get_plan_limit('events') is not None else 'Illimite',
        'plan_sermon_limit_display': church.get_plan_limit('sermons') if church.get_plan_limit('sermons') is not None else 'Illimite',
        'plan_page_limit_display': church.get_plan_limit('pages') if church.get_plan_limit('pages') is not None else 'Illimite',
        'plan_user_limit_display': church.get_plan_limit('users') if church.get_plan_limit('users') is not None else 'Illimite',
        'plan_pending_invitation_limit_display': church.get_plan_limit('pending_invitations') if church.get_plan_limit('pending_invitations') is not None else 'Illimite',
        'plan_storage_limit_display': (
            f"{church.get_plan_limit('storage_mb')} Mo"
            if church.get_plan_limit('storage_mb') is not None
            else 'Illimite'
        ),
        'upcoming_events': church.events.filter(
            is_active=True,
            event_date__gte=timezone.now().date()
        )[:5],
        'recent_messages': recent_messages[:5],
        'unread_messages_count': recent_messages.count(),
    }
    return render(request, 'admin_dashboard/dashboard.html', context)


@login_required
@require_capability(CAP_MANAGE_CHURCH_SETTINGS)
def church_settings(request):
    """Paramètres de l'église (nom, logo, couleurs, etc.)."""
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    if request.method == 'POST':
        form = ChurchForm(request.POST, request.FILES, instance=church)
        if form.is_valid():
            try:
                enforce_limits_for_model(church, Church, instance=church, form=form)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                form.save()
                try:
                    log_audit(
                        actor=request.user,
                        church=church,
                        action="settings_update",
                        instance=church,
                        metadata={"section": "church_settings"},
                    )
                except Exception:
                    pass
                if is_ajax(request):
                    return JsonResponse({'success': True, 'message': 'Paramètres mis à jour avec succès !'})
                messages.success(request, 'Paramètres mis à jour avec succès !')
                return redirect('church_settings')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = ChurchForm(instance=church)

    return render(request, 'admin_dashboard/church_settings.html', {
        'church': church,
        'form': form,
    })


# --- CRUD Événements ---

@login_required
@require_capability(CAP_MANAGE_EVENTS)
def manage_events(request):
    """Liste des événements (dashboard)."""
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    events = church.events.all()
    q = _get_text_param(request, 'q', 100)
    if q:
        events = events.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(location__icontains=q)
        )
    status = _get_choice_param(request, 'status', {'active', 'inactive'})
    if status == 'active':
        events = events.filter(is_active=True)
    elif status == 'inactive':
        events = events.filter(is_active=False)
    visibility = _get_choice_param(request, 'visibility', {'public', 'private', 'draft'})
    if visibility:
        events = events.filter(visibility=visibility)
    featured = _parse_bool_param(request.GET.get('featured'))
    if featured is True:
        events = events.filter(is_featured=True)
    elif featured is False:
        events = events.filter(is_featured=False)
    when = _get_choice_param(request, 'when', {'upcoming', 'past'})
    today = timezone.now().date()
    if when == 'upcoming':
        events = events.filter(event_date__gte=today)
    elif when == 'past':
        events = events.filter(event_date__lt=today)
    paginator = Paginator(events, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_events.html', {
        'church': church,
        'events': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
@require_capability(CAP_MANAGE_EVENTS)
def add_event(request):
    """Ajouter un événement."""
    def _after_save(event, created):
        notify_event_recipients(
            event.church,
            category="event",
            title="Événement créé" if created else "Événement mis à jour",
            body=event.title,
            link=reverse('manage_events'),
            exclude=request.user,
        )

    return _handle_church_form(
        request,
        form_class=EventForm,
        template_name='admin_dashboard/event_form.html',
        success_message='Événement ajouté !',
        success_url_name='manage_events',
        title='Ajouter un événement',
        after_save=_after_save,
    )


@login_required
@require_capability(CAP_MANAGE_EVENTS)
def edit_event(request, pk):
    """Modifier un événement."""
    def _after_save(event, created):
        notify_event_recipients(
            event.church,
            category="event",
            title="Événement mis à jour",
            body=event.title,
            link=reverse('manage_events'),
            exclude=request.user,
        )

    return _handle_church_form(
        request,
        form_class=EventForm,
        template_name='admin_dashboard/event_form.html',
        success_message='Événement modifié !',
        success_url_name='manage_events',
        title="Modifier l'événement",
        model=Event,
        pk=pk,
        object_name='event',
        after_save=_after_save,
    )


@login_required
@require_capability(CAP_MANAGE_EVENTS)
def delete_event(request, pk):
    """Supprimer un événement."""
    def _after_delete(event):
        notify_event_recipients(
            event.church,
            category="event",
            title="Événement supprimé",
            body=event.title,
            link=reverse('manage_events'),
            exclude=request.user,
        )

    return _handle_church_delete(
        request,
        model=Event,
        pk=pk,
        success_message='Événement supprimé !',
        success_url_name='manage_events',
        after_delete=_after_delete,
    )


# --- CRUD Prédications ---

@login_required
@require_capability(CAP_MANAGE_SERMONS)
def manage_sermons(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    sermons = church.sermons.all()
    q = _get_text_param(request, 'q', 100)
    if q:
        sermons = sermons.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(preacher__icontains=q) |
            Q(bible_reference__icontains=q)
        )
    status = _get_choice_param(request, 'status', {'active', 'inactive'})
    if status == 'active':
        sermons = sermons.filter(is_active=True)
    elif status == 'inactive':
        sermons = sermons.filter(is_active=False)
    visibility = _get_choice_param(request, 'visibility', {'public', 'private', 'draft'})
    if visibility:
        sermons = sermons.filter(visibility=visibility)
    featured = _parse_bool_param(request.GET.get('featured'))
    if featured is True:
        sermons = sermons.filter(is_featured=True)
    elif featured is False:
        sermons = sermons.filter(is_featured=False)
    paginator = Paginator(sermons, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_sermons.html', {
        'church': church,
        'sermons': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
@require_capability(CAP_MANAGE_SERMONS)
def add_sermon(request):
    return _handle_church_form(
        request,
        form_class=SermonForm,
        template_name='admin_dashboard/sermon_form.html',
        success_message='Prédication ajoutée !',
        success_url_name='manage_sermons',
        title='Ajouter une prédication',
    )


@login_required
@require_capability(CAP_MANAGE_SERMONS)
def edit_sermon(request, pk):
    return _handle_church_form(
        request,
        form_class=SermonForm,
        template_name='admin_dashboard/sermon_form.html',
        success_message='Prédication modifiée !',
        success_url_name='manage_sermons',
        title='Modifier la prédication',
        model=Sermon,
        pk=pk,
        object_name='sermon',
    )


@login_required
@require_capability(CAP_MANAGE_SERMONS)
def delete_sermon(request, pk):
    return _handle_church_delete(
        request,
        model=Sermon,
        pk=pk,
        success_message='Prédication supprimée !',
        success_url_name='manage_sermons',
    )


# --- CRUD Membres ---

@login_required
@require_capability(CAP_MANAGE_MEMBERS)
def manage_members(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    members = church.members.all()
    q = _get_text_param(request, 'q', 100)
    if q:
        members = members.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q)
        )
    status = _get_choice_param(request, 'status', {'active', 'inactive'})
    if status == 'active':
        members = members.filter(is_active=True)
    elif status == 'inactive':
        members = members.filter(is_active=False)
    gender = _get_choice_param(request, 'gender', {'M', 'F'})
    if gender in ('M', 'F'):
        members = members.filter(gender=gender)
    department = _get_text_param(request, 'department', 100)
    if department:
        members = members.filter(department__icontains=department)
    consent = _get_choice_param(request, 'consent', {'yes', 'no'})
    if consent == 'yes':
        members = members.filter(directory_consent=True)
    elif consent == 'no':
        members = members.filter(directory_consent=False)
    paginator = Paginator(members, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_members.html', {
        'church': church,
        'members': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
@require_capability(CAP_MANAGE_MEMBERS)
def add_member(request):
    return _handle_church_form(
        request,
        form_class=MemberForm,
        template_name='admin_dashboard/member_form.html',
        success_message='Membre ajouté !',
        success_url_name='manage_members',
        title='Ajouter un membre',
    )


@login_required
@require_capability(CAP_MANAGE_MEMBERS)
def edit_member(request, pk):
    return _handle_church_form(
        request,
        form_class=MemberForm,
        template_name='admin_dashboard/member_form.html',
        success_message='Membre modifié !',
        success_url_name='manage_members',
        title='Modifier le membre',
        model=Member,
        pk=pk,
        object_name='member',
    )


@login_required
@require_capability(CAP_MANAGE_MEMBERS)
def delete_member(request, pk):
    return _handle_church_delete(
        request,
        model=Member,
        pk=pk,
        success_message='Membre supprimé !',
        success_url_name='manage_members',
    )


# --- CRUD Pages ---

@login_required
@require_capability(CAP_MANAGE_PAGES)
def manage_pages(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    pages = church.pages.all()
    q = _get_text_param(request, 'q', 100)
    if q:
        pages = pages.filter(
            Q(title__icontains=q) |
            Q(slug__icontains=q)
        )
    status = _get_choice_param(request, 'status', {'active', 'inactive'})
    if status == 'active':
        pages = pages.filter(is_active=True)
    elif status == 'inactive':
        pages = pages.filter(is_active=False)
    visibility = _get_choice_param(request, 'visibility', {'public', 'private', 'draft'})
    if visibility:
        pages = pages.filter(visibility=visibility)
    in_menu = _parse_bool_param(request.GET.get('in_menu'))
    if in_menu is True:
        pages = pages.filter(is_in_menu=True)
    elif in_menu is False:
        pages = pages.filter(is_in_menu=False)
    paginator = Paginator(pages, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_pages.html', {
        'church': church,
        'pages': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
@require_capability(CAP_MANAGE_PAGES)
def add_page(request):
    return _handle_church_form(
        request,
        form_class=PageForm,
        template_name='admin_dashboard/page_form.html',
        success_message='Page ajoutée !',
        success_url_name='manage_pages',
        title='Ajouter une page',
    )


@login_required
@require_capability(CAP_MANAGE_PAGES)
def edit_page(request, pk):
    return _handle_church_form(
        request,
        form_class=PageForm,
        template_name='admin_dashboard/page_form.html',
        success_message='Page modifiée !',
        success_url_name='manage_pages',
        title='Modifier la page',
        model=Page,
        pk=pk,
        object_name='page',
    )


@login_required
@require_capability(CAP_MANAGE_PAGES)
def delete_page(request, pk):
    return _handle_church_delete(
        request,
        model=Page,
        pk=pk,
        success_message='Page supprimée !',
        success_url_name='manage_pages',
    )


# --- Utilisateurs & Rôles ---

@login_required
@require_capability(CAP_MANAGE_USERS)
def manage_users(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    ChurchInvitation.objects.filter(
        church=church,
        status=ChurchInvitation.Status.PENDING,
        expires_at__lt=timezone.now(),
    ).update(status=ChurchInvitation.Status.EXPIRED)
    memberships = ChurchMembership.objects.filter(church=church).select_related('user')
    pending_invites = ChurchInvitation.objects.filter(
        church=church,
        status=ChurchInvitation.Status.PENDING,
    ).order_by('-created_at')
    q = _get_text_param(request, 'q', 100)
    if q:
        memberships = memberships.filter(
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q)
        )
    role = _get_choice_param(request, 'role', {r for r, _ in ChurchMembership.Role.choices})
    if role:
        memberships = memberships.filter(role=role)
    status = _get_choice_param(request, 'status', {'active', 'inactive'})
    if status == 'active':
        memberships = memberships.filter(is_active=True)
    elif status == 'inactive':
        memberships = memberships.filter(is_active=False)
    paginator = Paginator(memberships.order_by('user__last_name', 'user__first_name'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_users.html', {
        'church': church,
        'memberships': page_obj,
        'page_obj': page_obj,
        'pending_invites': pending_invites,
        'querystring': _querystring_without_page(request),
    })


@login_required
@require_capability(CAP_MANAGE_USERS)
def add_user(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    if request.method == 'POST':
        form = ChurchUserCreateForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(church=church)
                    role = form.cleaned_data['role']

                    def after_commit():
                        try:
                            log_audit(
                                actor=request.user,
                                church=church,
                                action="membership_create",
                                object_type="ChurchMembership",
                                object_id=str(user.pk),
                                object_repr=str(user),
                                metadata={"role": role},
                            )
                        except Exception:
                            pass
                        notify_user_role_change(
                            church,
                            user,
                            title="Acc?s accord?",
                            body=f"Vous avez ?t? ajout?(e) comme {role} pour {church.name}.",
                            link=reverse('dashboard'),
                            actor=request.user,
                        )

                    _schedule_safe_after_commit(after_commit)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if is_ajax(request):
                    return JsonResponse({'success': True, 'message': 'Utilisateur cr?? !', 'redirect': reverse('manage_users')})
                messages.success(request, 'Utilisateur cr?? !')
                return redirect('manage_users')
        if is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = ChurchUserCreateForm()

    return render(request, 'admin_dashboard/user_form.html', {
        'church': church,
        'form': form,
        'title': "Ajouter un utilisateur",
    })


@login_required
@require_capability(CAP_MANAGE_USERS)
def assign_user(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    if request.method == 'POST':
        form = ChurchMembershipAssignForm(request.POST, church=church)
        if form.is_valid():
            try:
                with transaction.atomic():
                    membership = form.save(church=church)
                    created = getattr(form, 'created', False)
                    action_title = "Acc?s accord?" if created else "R?le mis ? jour"
                    audit_action = "membership_assign" if created else "membership_update"

                    def after_commit():
                        try:
                            log_audit(
                                actor=request.user,
                                church=church,
                                action=audit_action,
                                instance=membership,
                                metadata={"role": membership.role},
                            )
                        except Exception:
                            pass
                        notify_user_role_change(
                            church,
                            membership.user,
                            title=action_title,
                            body=f"Votre r?le pour {church.name} est maintenant {membership.get_role_display()}",
                            link=reverse('dashboard'),
                            actor=request.user,
                        )

                    _schedule_safe_after_commit(after_commit)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if is_ajax(request):
                    return JsonResponse({'success': True, 'message': 'Utilisateur assign? !', 'redirect': reverse('manage_users')})
                messages.success(request, 'Utilisateur assign? !')
                return redirect('manage_users')
        if is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = ChurchMembershipAssignForm(church=church)

    return render(request, 'admin_dashboard/assign_user.html', {
        'church': church,
        'form': form,
        'title': "Assigner un utilisateur",
    })


@login_required
@require_capability(CAP_MANAGE_USERS)
def invite_user(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    if request.method == 'POST':
        form = ChurchInvitationForm(request.POST, church=church, invited_by=request.user)
        if form.is_valid():
            invite = form.save()
            try:
                log_audit(
                    actor=request.user,
                    church=church,
                    action="invite_create",
                    instance=invite,
                    metadata={"email": invite.email, "role": invite.role},
                )
            except Exception:
                pass
            notify_church_admins(
                church,
                category="invite",
                title="Invitation envoy?e",
                body=f"{invite.email} - {invite.get_role_display()}",
                link=reverse('manage_users'),
                exclude=request.user,
            )
            User = get_user_model()
            invited_user = User.objects.filter(email__iexact=invite.email).first()
            if invited_user:
                notify_user(
                    invited_user,
                    church,
                    category="invite",
                    title="Invitation ? rejoindre l'?glise",
                    body=f"Invitation pour {church.name} ({invite.get_role_display()}).",
                    link=reverse('accept_invite', args=[invite.token]),
                )
            email_error = False
            try:
                _send_invite_email(request, invite)
            except Exception:
                email_error = True
                messages.error(request, "Invitation cr??e, mais l'email n'a pas pu ?tre envoy?.")
            if is_ajax(request):
                message = "Invitation envoy?e." if not email_error else "Invitation cr??e, email non envoy?."
                return JsonResponse({'success': True, 'message': message, 'redirect': reverse('manage_users')})
            if not email_error:
                messages.success(request, "Invitation envoy?e.")
            return redirect('manage_users')
        if is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = ChurchInvitationForm(church=church, invited_by=request.user)

    return render(request, 'admin_dashboard/invite_user.html', {
        'church': church,
        'form': form,
        'title': "Inviter un utilisateur",
    })


@login_required
@require_capability(CAP_MANAGE_USERS)
def revoke_invite(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    invite = get_object_or_404(ChurchInvitation, pk=pk, church=church)
    if request.method == 'POST' and invite.status == ChurchInvitation.Status.PENDING:
        invite.status = ChurchInvitation.Status.REVOKED
        invite.save(update_fields=['status'])
        try:
            log_audit(
                actor=request.user,
                church=church,
                action="invite_revoke",
                instance=invite,
                metadata={"email": invite.email},
            )
        except Exception:
            pass
        invited_user = get_user_model().objects.filter(email__iexact=invite.email).first()
        if invited_user:
            _mark_invite_notifications_read(invited_user, invite)
        notify_church_admins(
            church,
            category="invite",
            title="Invitation r?voqu?e",
            body=f"{invite.email} - {invite.get_role_display()}",
            link=reverse('manage_users'),
            exclude=request.user,
        )
        messages.success(request, "Invitation r?voqu?e.")
    return redirect('manage_users')


@login_required
@require_capability(CAP_MANAGE_USERS)
def resend_invite(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    invite = get_object_or_404(ChurchInvitation, pk=pk, church=church)
    if request.method == 'POST' and invite.status == ChurchInvitation.Status.PENDING:
        invite.expires_at = timezone.now() + timedelta(days=7)
        invite.save(update_fields=['expires_at'])
        try:
            log_audit(
                actor=request.user,
                church=church,
                action="invite_resend",
                instance=invite,
                metadata={"email": invite.email},
            )
        except Exception:
            pass
        try:
            _send_invite_email(request, invite)
            notify_church_admins(
                church,
                category="invite",
                title="Invitation renvoy?e",
                body=f"{invite.email} - {invite.get_role_display()}",
                link=reverse('manage_users'),
                exclude=request.user,
            )
            messages.success(request, "Invitation renvoy?e.")
        except Exception:
            messages.error(request, "Impossible d'envoyer l'email pour le moment.")
    return redirect('manage_users')


@login_required
@require_capability(CAP_MANAGE_USERS)
def toggle_membership(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    membership = get_object_or_404(ChurchMembership.objects.select_related('user'), pk=pk, church=church)
    if request.method != 'POST':
        return redirect('manage_users')
    action = request.POST.get('action')
    if action not in {'activate', 'deactivate'}:
        messages.error(request, "Action invalide.")
        return redirect('manage_users')

    try:
        with transaction.atomic():
            membership = get_object_or_404(
                ChurchMembership.objects.select_for_update().select_related('user'),
                pk=pk,
                church=church,
            )
            if action == 'deactivate' and membership.is_active:
                if membership.role == ChurchMembership.Role.ADMIN and not _has_other_admins(church, exclude_membership=membership):
                    messages.error(request, "Au moins un administrateur actif est requis.")
                    return redirect('manage_users')
                membership.is_active = False
            elif action == 'activate':
                if not membership.is_active:
                    enforce_limits_for_model(church, ChurchMembership)
                membership.is_active = True
            membership.save(update_fields=['is_active'])
            status_label = "actif" if membership.is_active else "inactif"

            def after_commit():
                try:
                    log_audit(
                        actor=request.user,
                        church=church,
                        action="membership_status",
                        instance=membership,
                        metadata={"active": membership.is_active},
                    )
                except Exception:
                    pass
                notify_user_role_change(
                    church,
                    membership.user,
                    title="Statut utilisateur mis ? jour",
                    body=f"Votre acc?s est maintenant {status_label} pour {church.name}.",
                    link=reverse('dashboard'),
                    actor=request.user,
                )

            _schedule_safe_after_commit(after_commit)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect('manage_users')

    messages.success(request, "Statut utilisateur mis ? jour.")
    return redirect('manage_users')


@login_required
@require_capability(CAP_MANAGE_USERS)
def transfer_admin(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    current_membership = get_membership(request.user, church)
    if not current_membership or current_membership.role != ChurchMembership.Role.ADMIN or not current_membership.is_active:
        messages.error(request, "Transfert r?serv? aux administrateurs actifs.")
        return redirect('manage_users')

    form = TransferAdminForm(
        request.POST or None,
        church=church,
        current_membership=current_membership,
    )
    if not form.fields['membership'].queryset.exists():
        messages.error(request, "Aucun autre membre actif disponible pour le transfert.")
        return redirect('manage_users')

    if request.method == 'POST':
        if form.is_valid():
            target_id = form.cleaned_data['membership'].pk
            with transaction.atomic():
                current_membership = get_object_or_404(
                    ChurchMembership.objects.select_for_update().select_related('user'),
                    pk=current_membership.pk,
                    church=church,
                )
                target = get_object_or_404(
                    ChurchMembership.objects.select_for_update().select_related('user'),
                    pk=target_id,
                    church=church,
                )
                target.role = ChurchMembership.Role.ADMIN
                target.is_active = True
                target.save(update_fields=['role', 'is_active'])
                if current_membership.pk != target.pk:
                    current_membership.role = ChurchMembership.Role.STAFF
                    current_membership.save(update_fields=['role'])

                def after_commit():
                    try:
                        log_audit(
                            actor=request.user,
                            church=church,
                            action="membership_transfer_admin",
                            instance=target,
                            metadata={"from_user": current_membership.user_id},
                        )
                    except Exception:
                        pass
                    notify_user_role_change(
                        church,
                        target.user,
                        title="Administration transf?r?e",
                        body=f"Vous ?tes maintenant administrateur de {church.name}.",
                        link=reverse('manage_users'),
                        actor=request.user,
                    )
                    if current_membership.user != target.user:
                        notify_user_role_change(
                            church,
                            current_membership.user,
                            title="Administration transf?r?e",
                            body=f"Votre r?le est maintenant {current_membership.get_role_display()} pour {church.name}.",
                            link=reverse('manage_users'),
                            actor=request.user,
                        )

                _schedule_safe_after_commit(after_commit)
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Administrateur transf?r?.', 'redirect': reverse('manage_users')})
            messages.success(request, "Administrateur transf?r?.")
            return redirect('manage_users')
        if is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    return render(request, 'admin_dashboard/transfer_admin.html', {
        'church': church,
        'form': form,
        'title': "Transf?rer l'administration",
    })


@login_required
@require_capability(CAP_MANAGE_USERS)
def edit_membership(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    membership = get_object_or_404(ChurchMembership, pk=pk, church=church)
    old_role = membership.role
    old_active = membership.is_active

    if request.method == 'POST':
        form = ChurchMembershipUpdateForm(request.POST, instance=membership)
        if form.is_valid():
            try:
                with transaction.atomic():
                    membership = get_object_or_404(
                        ChurchMembership.objects.select_for_update().select_related('user'),
                        pk=pk,
                        church=church,
                    )
                    old_role = membership.role
                    old_active = membership.is_active
                    form = ChurchMembershipUpdateForm(request.POST, instance=membership)
                    if not form.is_valid():
                        raise ValidationError(form.errors)
                    if not old_active and form.cleaned_data.get('is_active'):
                        enforce_limits_for_model(church, ChurchMembership)
                    membership = form.save()
                    if membership.role != old_role or membership.is_active != old_active:
                        status_label = "actif" if membership.is_active else "inactif"

                        def after_commit():
                            try:
                                log_audit(
                                    actor=request.user,
                                    church=church,
                                    action="membership_update",
                                    instance=membership,
                                    metadata={
                                        "role": membership.role,
                                        "active": membership.is_active,
                                    },
                                )
                            except Exception:
                                pass
                            notify_user_role_change(
                                church,
                                membership.user,
                                title="R?le mis ? jour",
                                body=f"R?le: {membership.get_role_display()} (statut: {status_label}).",
                                link=reverse('manage_users'),
                                actor=request.user,
                            )

                        _schedule_safe_after_commit(after_commit)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if is_ajax(request):
                    return JsonResponse({'success': True, 'message': 'R?le mis ? jour !', 'redirect': reverse('manage_users')})
                messages.success(request, 'R?le mis ? jour !')
                return redirect('manage_users')
        if is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = ChurchMembershipUpdateForm(instance=membership)

    return render(request, 'admin_dashboard/membership_form.html', {
        'church': church,
        'form': form,
        'title': "Modifier un utilisateur",
        'membership': membership,
    })


# --- Messages de contact ---

@login_required
@require_capability(CAP_MANAGE_MESSAGES)
def manage_messages(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    contact_messages = filter_messages_for_retention(
        church.messages.select_related('assigned_to'),
        church,
    )
    q = _get_text_param(request, 'q', 200)
    if q:
        contact_messages = contact_messages.filter(
            Q(sender_name__icontains=q) |
            Q(sender_email__icontains=q) |
            Q(subject__icontains=q) |
            Q(message__icontains=q)
        )
    status = _get_choice_param(request, 'status', {c for c, _ in ContactMessage.Status.choices})
    if status:
        contact_messages = contact_messages.filter(status=status)
    assigned = _get_choice_param(request, 'assigned', {'me', 'unassigned'})
    if assigned == 'me':
        contact_messages = contact_messages.filter(assigned_to=request.user)
    elif assigned == 'unassigned':
        contact_messages = contact_messages.filter(assigned_to__isnull=True)
    paginator = Paginator(contact_messages, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_messages.html', {
        'church': church,
        'contact_messages': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
@require_capability(CAP_MANAGE_MESSAGES)
def read_message(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    msg = get_object_or_404(
        filter_messages_for_retention(
            ContactMessage.objects.select_related('assigned_to', 'responded_by'),
            church,
        ),
        pk=pk,
        church=church,
    )
    reply_form = ContactMessageReplyForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_read':
            if msg.status == ContactMessage.Status.NEW:
                msg.status = ContactMessage.Status.READ
                msg.save(update_fields=['status', 'is_read'])
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Message marquÃ© comme lu.'})
            messages.success(request, 'Message marquÃ© comme lu.')
            return redirect('read_message', pk=pk)
        if action == 'archive':
            msg.status = ContactMessage.Status.ARCHIVED
            msg.archived_at = timezone.now()
            msg.save(update_fields=['status', 'archived_at', 'is_read'])
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Message archivÃ©.'})
            messages.success(request, 'Message archivÃ©.')
            return redirect('read_message', pk=pk)
        if action == 'assign_me':
            msg.assigned_to = request.user
            msg.save(update_fields=['assigned_to'])
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Message assignÃ©.'})
            messages.success(request, 'Message assignÃ©.')
            return redirect('read_message', pk=pk)
        if action == 'unassign':
            msg.assigned_to = None
            msg.save(update_fields=['assigned_to'])
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Assignation retirÃ©e.'})
            messages.success(request, "Assignation retirÃ©e.")
            return redirect('read_message', pk=pk)
        if action == 'respond':
            reply_form = ContactMessageReplyForm(request.POST)
            if reply_form.is_valid():
                reply = reply_form.save(commit=False)
                reply.message = msg
                reply.created_by = request.user
                reply.save()
                msg.status = ContactMessage.Status.RESPONDED
                msg.responded_at = timezone.now()
                msg.responded_by = request.user
                msg.save(update_fields=['status', 'responded_at', 'responded_by', 'is_read'])
                if is_ajax(request):
                    return JsonResponse({'success': True, 'message': 'RÃ©ponse enregistrÃ©e.'})
                messages.success(request, 'RÃ©ponse enregistrÃ©e.')
                return redirect('read_message', pk=pk)
            if is_ajax(request):
                return JsonResponse({'success': False, 'errors': reply_form.errors}, status=400)
        else:
            if is_ajax(request):
                return JsonResponse({'success': False, 'message': 'Action invalide.'}, status=400)
            messages.error(request, "Action invalide.")
            return redirect('read_message', pk=pk)
    return render(request, 'admin_dashboard/read_message.html', {
        'church': church,
        'msg': msg,
        'reply_form': reply_form,
        'replies': msg.replies.select_related('created_by'),
    })


# --- Notifications ---

@login_required
@require_capability(CAP_VIEW_DASHBOARD)
def manage_notifications(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    accessible_churches = list(get_accessible_churches(request.user))
    notifications = filter_notifications_for_retention(
        Notification.objects.filter(
            recipient=request.user,
            church__in=accessible_churches,
        ).select_related('church'),
        accessible_churches,
    )
    church_filter = request.GET.get('church')
    if church_filter:
        notifications = notifications.filter(church_id=church_filter, church__in=accessible_churches)
    status = _get_choice_param(request, 'status', {'read', 'unread'})
    if status == 'read':
        notifications = notifications.filter(is_read=True)
    elif status == 'unread':
        notifications = notifications.filter(is_read=False)
    category = _get_choice_param(request, 'category', {c for c, _ in Notification.Category.choices})
    if category:
        notifications = notifications.filter(category=category)
    paginator = Paginator(notifications, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/notifications.html', {
        'church': church,
        'churches': accessible_churches,
        'notifications': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
@require_capability(CAP_VIEW_DASHBOARD)
def open_notification(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    accessible_churches = list(get_accessible_churches(request.user))
    notification = get_object_or_404(
        filter_notifications_for_retention(
            Notification.objects.filter(
                recipient=request.user,
                church__in=accessible_churches,
            ),
            accessible_churches,
        ),
        pk=pk,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    target = notification.link
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(target)
    return redirect('manage_notifications')


@login_required
@require_capability(CAP_VIEW_DASHBOARD)
def mark_notification_read(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    accessible_churches = list(get_accessible_churches(request.user))
    notification = get_object_or_404(
        filter_notifications_for_retention(
            Notification.objects.filter(
                recipient=request.user,
                church__in=accessible_churches,
            ),
            accessible_churches,
        ),
        pk=pk,
    )
    if request.method == 'POST':
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return redirect('manage_notifications')


@login_required
@require_capability(CAP_VIEW_DASHBOARD)
def mark_all_notifications_read(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    if request.method == 'POST':
        accessible_churches = list(get_accessible_churches(request.user))
        filter_notifications_for_retention(
            Notification.objects.filter(
                recipient=request.user,
                is_read=False,
                church__in=accessible_churches,
            ),
            accessible_churches,
        ).update(is_read=True)
    return redirect('manage_notifications')


@login_required
@require_capability(CAP_VIEW_AUDIT)
def manage_audit_logs(request):
    churches = get_churches_for_capability(request.user, CAP_VIEW_AUDIT)
    logs = AuditLog.objects.select_related('actor', 'church')
    if not request.user.is_superuser:
        logs = logs.filter(church__in=churches)

    church_filter = request.GET.get('church')
    if church_filter == 'platform' and request.user.is_superuser:
        logs = logs.filter(church__isnull=True)
    elif church_filter:
        logs = logs.filter(church_id=church_filter)

    action = _get_text_param(request, 'action', 50)
    if action:
        logs = logs.filter(action__icontains=action)

    paginator = Paginator(logs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/audit_logs.html', {
        'church': getattr(request, 'current_church', None),
        'churches': churches,
        'logs': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
        'show_platform': request.user.is_superuser,
    })


# --- Paramètres globaux (super-admin uniquement) ---

@login_required
@require_capability(CAP_MANAGE_SITE_SETTINGS)
def site_settings(request):
    """Paramètres globaux de la plateforme (nom, slogan, etc.)."""
    settings_obj = SiteSettings.get()
    church = get_selected_church(request)

    if request.method == 'POST':
        form = SiteSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            form.save()
            try:
                log_audit(
                    actor=request.user,
                    church=None,
                    action="settings_update",
                    instance=settings_obj,
                    metadata={"section": "site_settings"},
                )
            except Exception:
                pass
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Paramètres de la plateforme mis à jour !'})
            messages.success(request, 'Paramètres de la plateforme mis à jour !')
            return redirect('site_settings')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = SiteSettingsForm(instance=settings_obj)

    return render(request, 'admin_dashboard/site_settings.html', {
        'church': church,
        'form': form,
        'site_settings': settings_obj,
    })
