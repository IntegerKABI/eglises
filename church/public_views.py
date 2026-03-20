"""Public-facing views and invitation flows."""

import logging

from django.contrib import messages

logger = logging.getLogger(__name__)
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone

from .audit import log_audit
from .forms import ContactForm, InviteSignupForm
from .limits import enforce_limits_for_model
from .membership_policy import get_pending_invitations_for_user, validate_single_church_membership
from .models import Church, ChurchInvitation, ChurchMembership, ContactMessage, Page, filter_public_queryset
from .notifications import notify_church_admins, notify_message_recipients, notify_user
from .tenancy import get_accessible_churches
from .view_helpers import _get_choice_param, _get_public_church, _get_text_param, _has_pending_invitations, _mark_invite_notifications_read, _parse_bool_param, _querystring_without_page, is_ajax


def home(request):
    """Render the public landing page with the list of active churches."""
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
    """Render the public homepage for a single church."""
    church = _get_public_church(request, church_slug)
    upcoming_events = filter_public_queryset(church.events.defer('description')).filter(
        event_date__gte=timezone.now().date()
    )[:3]
    latest_sermons = filter_public_queryset(church.sermons.defer('description'))[:3]
    custom_pages = filter_public_queryset(church.pages.defer('content')).filter(is_in_menu=True)

    return render(request, 'church/church_home.html', {
        'church': church,
        'upcoming_events': upcoming_events,
        'latest_sermons': latest_sermons,
        'custom_pages': custom_pages,
    })


def church_events(request, church_slug):
    """Render the public event listing for a church."""
    church = _get_public_church(request, church_slug)
    events = filter_public_queryset(church.events.defer('description'))
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
    """Render the public sermon listing for a church."""
    church = _get_public_church(request, church_slug)
    sermons = filter_public_queryset(church.sermons.defer('description'))
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
    """Render a custom public page for a church."""
    church = _get_public_church(request, church_slug)
    page = get_object_or_404(filter_public_queryset(Page.objects.filter(church=church, slug=page_slug)))
    return render(request, 'church/custom_page.html', {
        'church': church,
        'page': page,
    })


def church_contact(request, church_slug):
    """Handle the public contact form for a church."""
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
            logger.error("Failed to log invite_accept action", exc_info=True)
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
@require_POST
def decline_invite(request, token):
    invite = get_object_or_404(
        ChurchInvitation,
        token=token,
        status=ChurchInvitation.Status.PENDING,
        email__iexact=request.user.email,
    )
    if invite.is_expired:
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
        logger.error("Failed to log invite_decline action", exc_info=True)
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

