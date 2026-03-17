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

from django.shortcuts import render, get_object_or_404, redirect
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

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
    CAP_VIEW_DASHBOARD,
    require_capability,
)
from .tenancy import get_accessible_churches, get_membership, get_selected_church


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
            obj.save()
            if hasattr(form, 'save_m2m'):
                form.save_m2m()
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


def _handle_church_delete(request, model, pk, success_message, success_url_name):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    obj = get_object_or_404(model, pk=pk, church=church)
    if request.method == 'POST':
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
        return redirect('dashboard')
    if invite.church.status in {Church.Status.SUSPENDED, Church.Status.ARCHIVED}:
        messages.error(request, "Cette église n'accepte pas de nouvelles invitations.")
        return redirect('dashboard')
    if invite.is_expired:
        invite.status = ChurchInvitation.Status.EXPIRED
        invite.save(update_fields=['status'])
        messages.error(request, "Cette invitation a expiré.")
        return redirect('dashboard')

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
                membership.is_active = True
                membership.save(update_fields=['role', 'is_active'])
            else:
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
        messages.success(request, "Invitation acceptée. Bienvenue !")
        return redirect('dashboard')

    return render(request, 'church/accept_invite.html', {
        'invite': invite,
        'church': invite.church,
    })


@login_required
def select_church(request):
    churches = get_accessible_churches(request.user)
    if not churches.exists():
        messages.warning(request, "Aucune église associée à votre compte.")
        return redirect('home')

    if churches.count() == 1:
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

    context = {
        'church': church,
        'total_members': church.members.filter(is_active=True).count(),
        'total_events': church.events.filter(is_active=True).count(),
        'total_sermons': church.sermons.filter(is_active=True).count(),
        'upcoming_events': church.events.filter(
            is_active=True,
            event_date__gte=timezone.now().date()
        )[:5],
        'recent_messages': church.messages.filter(status=ContactMessage.Status.NEW)[:5],
        'unread_messages_count': church.messages.filter(status=ContactMessage.Status.NEW).count(),
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
            form.save()
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
    return _handle_church_form(
        request,
        form_class=EventForm,
        template_name='admin_dashboard/event_form.html',
        success_message='Événement ajouté !',
        success_url_name='manage_events',
        title='Ajouter un événement',
    )


@login_required
@require_capability(CAP_MANAGE_EVENTS)
def edit_event(request, pk):
    """Modifier un événement."""
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
    )


@login_required
@require_capability(CAP_MANAGE_EVENTS)
def delete_event(request, pk):
    """Supprimer un événement."""
    return _handle_church_delete(
        request,
        model=Event,
        pk=pk,
        success_message='Événement supprimé !',
        success_url_name='manage_events',
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
            form.save(church=church)
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Utilisateur créé !', 'redirect': reverse('manage_users')})
            messages.success(request, 'Utilisateur créé !')
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
            form.save(church=church)
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Utilisateur assigné !', 'redirect': reverse('manage_users')})
            messages.success(request, 'Utilisateur assigné !')
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
            email_error = False
            try:
                _send_invite_email(request, invite)
            except Exception:
                email_error = True
                messages.error(request, "Invitation créée, mais l'email n'a pas pu être envoyé.")
            if is_ajax(request):
                message = "Invitation envoyée." if not email_error else "Invitation créée, email non envoyé."
                return JsonResponse({'success': True, 'message': message, 'redirect': reverse('manage_users')})
            if not email_error:
                messages.success(request, "Invitation envoyée.")
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
        messages.success(request, "Invitation révoquée.")
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
            _send_invite_email(request, invite)
            messages.success(request, "Invitation renvoyée.")
        except Exception:
            messages.error(request, "Impossible d'envoyer l'email pour le moment.")
    return redirect('manage_users')


@login_required
@require_capability(CAP_MANAGE_USERS)
def toggle_membership(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    membership = get_object_or_404(ChurchMembership, pk=pk, church=church)
    if request.method != 'POST':
        return redirect('manage_users')
    action = request.POST.get('action')
    if action not in {'activate', 'deactivate'}:
        messages.error(request, "Action invalide.")
        return redirect('manage_users')
    if action == 'deactivate' and membership.is_active:
        if membership.role == ChurchMembership.Role.ADMIN and not _has_other_admins(church, exclude_membership=membership):
            messages.error(request, "Au moins un administrateur actif est requis.")
            return redirect('manage_users')
        membership.is_active = False
    elif action == 'activate':
        membership.is_active = True
    membership.save(update_fields=['is_active'])
    messages.success(request, "Statut utilisateur mis à jour.")
    return redirect('manage_users')


@login_required
@require_capability(CAP_MANAGE_USERS)
def transfer_admin(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    current_membership = get_membership(request.user, church)
    if not current_membership or current_membership.role != ChurchMembership.Role.ADMIN or not current_membership.is_active:
        messages.error(request, "Transfert réservé aux administrateurs actifs.")
        return redirect('manage_users')

    form = TransferAdminForm(
        request.POST or None,
        church=church,
        current_membership=current_membership,
    )
    if not form.fields['membership'].queryset.exists():
        messages.error(request, "Aucun autre membre actif disponible pour le transfert.")
        return redirect('manage_users')

    if request.method == 'POST' and form.is_valid():
        target = form.cleaned_data['membership']
        with transaction.atomic():
            target.role = ChurchMembership.Role.ADMIN
            target.is_active = True
            target.save(update_fields=['role', 'is_active'])
            if current_membership.pk != target.pk:
                current_membership.role = ChurchMembership.Role.STAFF
                current_membership.save(update_fields=['role'])
        messages.success(request, "Administrateur transféré.")
        return redirect('manage_users')

    return render(request, 'admin_dashboard/transfer_admin.html', {
        'church': church,
        'form': form,
        'title': "Transférer l'administration",
    })


@login_required
@require_capability(CAP_MANAGE_USERS)
def edit_membership(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    membership = get_object_or_404(ChurchMembership, pk=pk, church=church)

    if request.method == 'POST':
        form = ChurchMembershipUpdateForm(request.POST, instance=membership)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Rôle mis à jour !', 'redirect': reverse('manage_users')})
            messages.success(request, 'Rôle mis à jour !')
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
    contact_messages = church.messages.select_related('assigned_to')
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
        ContactMessage.objects.select_related('assigned_to', 'responded_by'),
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
