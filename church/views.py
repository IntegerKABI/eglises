"""Dashboard views and the historical public import surface for the church app."""

from datetime import timedelta
import logging

from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .audit import log_audit
from .forms import (
    ChurchForm,
    ChurchInvitationForm,
    ChurchMembershipAssignForm,
    ChurchMembershipUpdateForm,
    ChurchUserCreateForm,
    ContactMessageReplyForm,
    EventForm,
    MemberForm,
    PageForm,
    SermonForm,
    TransferAdminForm,
)
from .limits import enforce_limits_for_model, filter_messages_for_retention, get_plan_usage
from .models import Church, ChurchInvitation, ChurchMembership, ContactMessage, Event, Member, Page, Sermon
from .notifications import (
    notify_church_admins,
    notify_event_recipients,
    notify_message_recipients,
    notify_user,
    notify_user_role_change,
)
from .permissions import (
    CAP_MANAGE_CHURCH_SETTINGS,
    CAP_MANAGE_EVENTS,
    CAP_MANAGE_MEMBERS,
    CAP_MANAGE_MESSAGES,
    CAP_MANAGE_PAGES,
    CAP_MANAGE_SERMONS,
    CAP_MANAGE_USERS,
    CAP_VIEW_DASHBOARD,
    get_capabilities_for_user,
    require_capability,
)
from .rate_limits import (
    build_invite_send_rate_limit_rules,
    build_rate_limit_message,
    consume_rate_limits,
)
from .public_views import (
    accept_invite,
    church_contact,
    church_events,
    church_home,
    church_page,
    church_sermons,
    decline_invite,
    home,
    pending_invitations,
    select_church,
)
from .notification_views import (
    manage_audit_logs,
    manage_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    open_notification,
    site_settings,
)
from .superadmin_views import (
    superadmin_church_create,
    superadmin_church_detail,
    superadmin_church_edit,
    superadmin_church_list,
    superadmin_church_plan,
    superadmin_church_status,
    superadmin_switch_church,
)
from .tenancy import get_membership
from .view_helpers import (
    TenantLoginView,
    _get_choice_param,
    _get_text_param,
    _parse_bool_param,
    _has_other_admins,
    _mark_invite_notifications_read,
    _handle_church_delete,
    _handle_church_form,
    _enqueue_invite_email_delivery,
    _querystring_without_page,
    _require_church,
    _schedule_safe_after_commit,
    is_ajax,
)


@login_required
@require_capability(CAP_VIEW_DASHBOARD)
def dashboard(request):
    """Render the role-aware dashboard overview for the current church."""
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    membership = getattr(request, 'current_membership', None)
    if membership is None and request.user.is_authenticated and not request.user.is_superuser:
        membership = get_membership(request.user, church)
        request.current_membership = membership

    capabilities = get_capabilities_for_user(request.user, membership)
    can_manage_messages = request.user.is_superuser or CAP_MANAGE_MESSAGES in capabilities
    can_manage_members = request.user.is_superuser or CAP_MANAGE_MEMBERS in capabilities
    can_manage_pages = request.user.is_superuser or CAP_MANAGE_PAGES in capabilities
    can_manage_church_settings = (
        request.user.is_superuser or CAP_MANAGE_CHURCH_SETTINGS in capabilities
    )

    recent_messages = filter_messages_for_retention(
        church.messages.filter(status=ContactMessage.Status.NEW).select_related('assigned_to', 'responded_by'),
        church,
    ) if can_manage_messages else church.messages.none()
    assigned_messages = filter_messages_for_retention(
        church.messages.filter(assigned_to=request.user).select_related('assigned_to', 'responded_by'),
        church,
    ) if can_manage_messages else church.messages.none()
    recent_sermons = church.sermons.filter(is_active=True).select_related('created_by').defer('description', 'video_url', 'audio_url').order_by('-created_at')[:5]
    recent_pages = church.pages.filter(is_active=True).select_related('created_by').defer('content').order_by('sort_order', 'title')[:5]
    recent_members = church.members.filter(is_active=True).defer('address', 'phone').order_by('-created_at')[:5]
    plan_usage = get_plan_usage(church)

    context = {
        'church': church,
        'capabilities': capabilities,
        'show_plan_summary': can_manage_church_settings,
        'show_message_overview': can_manage_messages,
        'show_member_overview': can_manage_members,
        'show_page_overview': can_manage_pages,
        'total_members': church.members.filter(is_active=True).count(),
        'total_events': church.events.filter(is_active=True).count(),
        'total_sermons': church.sermons.filter(is_active=True).count(),
        'total_pages': church.pages.filter(is_active=True).count(),
        'plan_usage': plan_usage,
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
        'assigned_messages_count': assigned_messages.count(),
        'recent_sermons': recent_sermons,
        'recent_pages': recent_pages,
        'recent_members': recent_members,
        'draft_page_count': church.pages.filter(is_active=True, visibility='draft').count(),
        'draft_sermon_count': church.sermons.filter(is_active=True, visibility='draft').count(),
    }
    return render(request, 'admin_dashboard/dashboard.html', context)


@login_required
@require_capability(CAP_MANAGE_CHURCH_SETTINGS)
def church_settings(request):
    """Manage church-level branding and profile settings."""
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
                    logger.error("Failed to log settings_update action", exc_info=True)
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


@login_required
@require_capability(CAP_MANAGE_EVENTS)
def manage_events(request):
    """Render the dashboard event listing with filtering and pagination."""
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    events = church.events.select_related('created_by').defer('description').all()
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
    """Create a new church event from the dashboard."""
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
    """Update an existing church event from the dashboard."""
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
    """Delete a church event from the dashboard."""
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


@login_required
@require_capability(CAP_MANAGE_SERMONS)
def manage_sermons(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    sermons = church.sermons.select_related('created_by').defer('description').all()
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


@login_required
@require_capability(CAP_MANAGE_MEMBERS)
def manage_members(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    members = church.members.defer('address').all()
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


@login_required
@require_capability(CAP_MANAGE_PAGES)
def manage_pages(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    pages = church.pages.select_related('created_by').defer('content').all()
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


@login_required
@require_capability(CAP_MANAGE_USERS)
def manage_users(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    memberships = ChurchMembership.objects.filter(church=church).select_related('user')
    pending_invites = ChurchInvitation.objects.filter(
        church=church,
        status=ChurchInvitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).select_related('invited_by', 'accepted_by').order_by('-created_at')
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
                            logger.error("Failed to log membership_create action", exc_info=True)
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
                            logger.error("Failed to log membership_assign action", exc_info=True)
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
        throttle_result = consume_rate_limits(
            build_invite_send_rate_limit_rules(request, request.user, f"church:{church.pk}")
        )
        if throttle_result.limited:
            message = build_rate_limit_message(throttle_result.retry_after_seconds)
            if is_ajax(request):
                return JsonResponse({'success': False, 'message': message}, status=429)
            messages.error(request, message)
            return redirect('manage_users')
        form = ChurchInvitationForm(request.POST, church=church, invited_by=request.user)
        if form.is_valid():
            with transaction.atomic():
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
                    logger.error("Failed to log invite_create action", exc_info=True)
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
                _enqueue_invite_email_delivery(request, invite)
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': "Invitation envoy?e.", 'redirect': reverse('manage_users')})
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
            logger.error("Failed to log invite_revoke action", exc_info=True)
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
        throttle_result = consume_rate_limits(
            build_invite_send_rate_limit_rules(request, request.user, f"church:{church.pk}")
        )
        if throttle_result.limited:
            messages.error(request, build_rate_limit_message(throttle_result.retry_after_seconds))
            return redirect('manage_users')
        with transaction.atomic():
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
                logger.error("Failed to log invite_resend action", exc_info=True)
            _enqueue_invite_email_delivery(request, invite)
            notify_church_admins(
                church,
                category="invite",
                title="Invitation renvoy?e",
                body=f"{invite.email} - {invite.get_role_display()}",
                link=reverse('manage_users'),
                exclude=request.user,
            )
        messages.success(request, "Invitation renvoy?e.")
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
                    logger.error("Failed to log membership_status action", exc_info=True)
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
                        logger.error("Failed to log membership_transfer_admin action", exc_info=True)
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
                                logger.error("Failed to log membership_update action", exc_info=True)
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
    if request.method == 'GET' and msg.status == ContactMessage.Status.NEW:
        msg.status = ContactMessage.Status.READ
        msg.save(update_fields=['status', 'is_read'])
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
