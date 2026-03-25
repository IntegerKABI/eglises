"""Public-facing views and invitation flows."""

from datetime import timedelta
import logging

from django.conf import settings
from django.contrib import messages

logger = logging.getLogger(__name__)
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone
from .cache import cache_public_view, get_church_cache_version

from .audit import log_audit_safely
from .background_jobs import enqueue_contact_email_job
from .forms import ContactForm, InviteSignupForm
from .invitation_services import accept_invitation
from .membership_policy import get_pending_invitations_for_user, validate_single_church_membership
from .models import Church, ChurchInvitation, ContactMessage, Page, filter_public_queryset
from .notifications import (
    notify_church_admins,
    notify_contact_recipients,
    notify_user,
    resolve_contact_recipient_groups,
)
from .rate_limits import (
    build_contact_rate_limit_rules,
    build_invite_accept_rate_limit_rules,
    build_rate_limit_message,
    consume_rate_limits,
)
from .tenancy import get_accessible_churches
from .view_helpers import _get_choice_param, _get_public_church, _get_text_param, _has_pending_invitations, _mark_invite_notifications_read, _parse_bool_param, _querystring_without_page, is_ajax
from .view_helpers import ajax_error_response, ajax_form_error_response, ajax_success_response


def _home_key(request):
    return f"global_home_v{get_church_cache_version(None)}"

@cache_public_view(_home_key)
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


def _church_home_key(request, church_slug):
    return f"c_{church_slug}_home_v{get_church_cache_version(church_slug)}"

@cache_public_view(_church_home_key)
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


def _church_events_key(request, church_slug):
    return f"c_{church_slug}_evt_v{get_church_cache_version(church_slug)}"

@cache_public_view(_church_events_key)
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


def _church_sermons_key(request, church_slug):
    return f"c_{church_slug}_srm_v{get_church_cache_version(church_slug)}"

@cache_public_view(_church_sermons_key)
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


def _church_page_key(request, church_slug, page_slug):
    return f"c_{church_slug}_pg_{page_slug}_v{get_church_cache_version(church_slug)}"

@cache_public_view(_church_page_key)
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
        throttle_result = consume_rate_limits(
            build_contact_rate_limit_rules(request, church, request.POST.get("sender_email"))
        )
        if throttle_result.limited:
            message = build_rate_limit_message(throttle_result.retry_after_seconds)
            if is_ajax(request):
                return ajax_error_response(
                    message=message,
                    code="rate_limited",
                    http_status=429,
                )
            messages.error(request, message)
            return redirect('church_contact', church_slug=church_slug)
        form = ContactForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.church = church
            with transaction.atomic():
                message.save()
                primary_recipients, escalation_recipients = resolve_contact_recipient_groups(
                    church,
                    title="Nouveau message reçu",
                    body=f"{message.sender_name} - {message.subject or 'Sans sujet'}",
                    source_text=message.message,
                )
                notify_contact_recipients(
                    church,
                    category="message",
                    title="Nouveau message reçu",
                    body=f"{message.sender_name} - {message.subject or 'Sans sujet'}",
                    link=reverse('read_message', args=[message.pk]),
                    recipients=[*primary_recipients, *escalation_recipients],
                )
                enqueue_contact_email_job(
                    message,
                    primary_recipients,
                    request.build_absolute_uri(reverse('read_message', args=[message.pk])),
                )
                if escalation_recipients:
                    enqueue_contact_email_job(
                        message,
                        escalation_recipients,
                        request.build_absolute_uri(reverse('read_message', args=[message.pk])),
                        available_at=timezone.now() + timedelta(
                            seconds=getattr(settings, "CONTACT_EMAIL_ESCALATION_DELAY_SECONDS", 5)
                        ),
                    )
            if is_ajax(request):
                return ajax_success_response(
                    message='Votre message a été envoyé avec succès !',
                    code="contact_message_sent",
                )
            messages.success(request, 'Votre message a été envoyé avec succès !')
            return redirect('church_contact', church_slug=church_slug)
        elif is_ajax(request):
            return ajax_form_error_response(form)
    else:
        form = ContactForm()

    return render(request, 'church/contact.html', {
        'church': church,
        'form': form,
    })


def accept_invite(request, token):
    """Let an invited user accept access without exposing invitation internals."""
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
        messages.error(request, "Cette invitation a expiré.")
        if request.user.is_authenticated:
            return redirect('pending_invitations')
        return redirect('home')

    if request.method == 'POST':
        identity = request.user.email if request.user.is_authenticated else invite.email
        throttle_result = consume_rate_limits(
            build_invite_accept_rate_limit_rules(request, invite, identity)
        )
        if throttle_result.limited:
            messages.error(request, build_rate_limit_message(throttle_result.retry_after_seconds))
            return redirect('accept_invite', token=invite.token)

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
        accept_invitation(actor=request.user, invite=invite)
        messages.success(request, "Invitation acceptée. Bienvenue !")
        return redirect('dashboard')

    return render(request, 'church/accept_invite.html', {
        'invite': invite,
        'church': invite.church,
    })


@login_required
def pending_invitations(request):
    """Show pending invitations so a user can finish joining a church."""
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
    """Decline an invitation and keep the public workflow's state consistent."""
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
    log_audit_safely(
        actor=request.user,
        church=invite.church,
        action="invite_decline",
        instance=invite,
        metadata={"email": invite.email, "role": invite.role},
        error_message="Failed to log invite_decline action",
    )
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
    """Let a user choose the active church context when they belong to several."""
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

