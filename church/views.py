"""Dashboard views and the historical public import surface for the church app."""
import logging

logger = logging.getLogger(__name__)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

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
from .invitation_services import (
    create_invitation_from_form,
    resend_invitation as resend_invitation_service,
    revoke_invitation as revoke_invitation_service,
)
from .limits import enforce_limits_for_model, filter_messages_for_retention
from .membership_services import (
    assign_membership_from_form,
    set_membership_active_state,
    transfer_admin_role,
    update_membership,
)
from .message_services import (
    archive_message,
    assign_message_to_user,
    mark_message_as_read,
    respond_to_message,
    unassign_message,
)
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
from .query_helpers import (
    build_dashboard_context,
    build_manage_events_queryset,
    build_manage_messages_queryset,
    build_manage_members_queryset,
    build_manage_pages_queryset,
    build_manage_sermons_queryset,
    build_manage_users_querysets,
)
from .list_view_helpers import build_paginated_list_context
from .view_helpers import (
    TenantLoginView,
    _handle_church_delete,
    _handle_church_form,
    _require_church,
    _schedule_safe_after_commit,
    ajax_error_response,
    ajax_form_error_response,
    ajax_success_response,
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
    context = build_dashboard_context(church=church, user=request.user, capabilities=capabilities)
    context['capabilities'] = capabilities
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
                    return ajax_success_response(
                        message='Paramètres mis à jour avec succès !',
                        code="church_settings_updated",
                    )
                messages.success(request, 'Paramètres mis à jour avec succès !')
                return redirect('church_settings')
        elif is_ajax(request):
            return ajax_form_error_response(form)
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
    events = build_manage_events_queryset(request=request, church=church)
    context = build_paginated_list_context(request=request, queryset=events, per_page=10, item_key='events')
    context['church'] = church
    return render(request, 'admin_dashboard/manage_events.html', context)


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
    sermons = build_manage_sermons_queryset(request=request, church=church)
    context = build_paginated_list_context(request=request, queryset=sermons, per_page=10, item_key='sermons')
    context['church'] = church
    return render(request, 'admin_dashboard/manage_sermons.html', context)


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
    members = build_manage_members_queryset(request=request, church=church)
    context = build_paginated_list_context(request=request, queryset=members, per_page=10, item_key='members')
    context['church'] = church
    return render(request, 'admin_dashboard/manage_members.html', context)


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
    pages = build_manage_pages_queryset(request=request, church=church)
    context = build_paginated_list_context(request=request, queryset=pages, per_page=10, item_key='pages')
    context['church'] = church
    return render(request, 'admin_dashboard/manage_pages.html', context)


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
    memberships, pending_invites = build_manage_users_querysets(request=request, church=church)
    context = build_paginated_list_context(
        request=request,
        queryset=memberships.order_by('user__last_name', 'user__first_name'),
        per_page=10,
        item_key='memberships',
    )
    context['church'] = church
    context['pending_invites'] = pending_invites
    return render(request, 'admin_dashboard/manage_users.html', context)


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
                            title="Accès accordé",
                            body=f"Vous avez été ajouté(e) comme {role} pour {church.name}.",
                            link=reverse('dashboard'),
                            actor=request.user,
                        )

                    _schedule_safe_after_commit(after_commit)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if is_ajax(request):
                    return ajax_success_response(
                        message='Utilisateur créé !',
                        code="user_created",
                        redirect=reverse('manage_users'),
                    )
                messages.success(request, 'Utilisateur créé !')
                return redirect('manage_users')
        if is_ajax(request):
            return ajax_form_error_response(form)
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
                assign_membership_from_form(actor=request.user, church=church, form=form)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if is_ajax(request):
                    return ajax_success_response(
                        message='Utilisateur assigné !',
                        code="user_assigned",
                        redirect=reverse('manage_users'),
                    )
                messages.success(request, 'Utilisateur assigné !')
                return redirect('manage_users')
        if is_ajax(request):
            return ajax_form_error_response(form)
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
                return ajax_error_response(message=message, code="rate_limited", http_status=429)
            messages.error(request, message)
            return redirect('manage_users')
        form = ChurchInvitationForm(request.POST, church=church, invited_by=request.user)
        if form.is_valid():
            create_invitation_from_form(request=request, actor=request.user, church=church, form=form)
            if is_ajax(request):
                return ajax_success_response(
                    message="Invitation envoyée.",
                    code="invitation_sent",
                    redirect=reverse('manage_users'),
                )
            messages.success(request, "Invitation envoyée.")
            return redirect('manage_users')
        if is_ajax(request):
            return ajax_form_error_response(form)
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
        revoke_invitation_service(actor=request.user, church=church, invite=invite)
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
        throttle_result = consume_rate_limits(
            build_invite_send_rate_limit_rules(request, request.user, f"church:{church.pk}")
        )
        if throttle_result.limited:
            messages.error(request, build_rate_limit_message(throttle_result.retry_after_seconds))
            return redirect('manage_users')
        resend_invitation_service(request=request, actor=request.user, church=church, invite=invite)
        messages.success(request, "Invitation renvoyée.")
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
        set_membership_active_state(
            actor=request.user,
            church=church,
            membership_id=pk,
            is_active=(action == 'activate'),
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect('manage_users')

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
            transfer_admin_role(
                actor=request.user,
                church=church,
                current_membership_id=current_membership.pk,
                target_membership_id=form.cleaned_data['membership'].pk,
            )
            if is_ajax(request):
                return ajax_success_response(
                    message='Administrateur transféré.',
                    code="admin_transferred",
                    redirect=reverse('manage_users'),
                )
            messages.success(request, "Administrateur transféré.")
            return redirect('manage_users')
        if is_ajax(request):
            return ajax_form_error_response(form)

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
            try:
                membership = update_membership(
                    actor=request.user,
                    church=church,
                    membership_id=pk,
                    role=form.cleaned_data['role'],
                    is_active=form.cleaned_data['is_active'],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if is_ajax(request):
                    return ajax_success_response(
                        message='Rôle mis à jour !',
                        code="membership_updated",
                        redirect=reverse('manage_users'),
                    )
                messages.success(request, 'Rôle mis à jour !')
                return redirect('manage_users')
        if is_ajax(request):
            return ajax_form_error_response(form)
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
    contact_messages = build_manage_messages_queryset(request=request, church=church)
    context = build_paginated_list_context(
        request=request,
        queryset=contact_messages,
        per_page=10,
        item_key='contact_messages',
    )
    context['church'] = church
    return render(request, 'admin_dashboard/manage_messages.html', context)


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
    if request.method == 'GET':
        msg = mark_message_as_read(msg)
    reply_form = ContactMessageReplyForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_read':
            msg = mark_message_as_read(msg)
            if is_ajax(request):
                return ajax_success_response(message='Message marqué comme lu.', code="message_marked_read")
            messages.success(request, 'Message marqué comme lu.')
            return redirect('read_message', pk=pk)
        if action == 'archive':
            msg = archive_message(msg)
            if is_ajax(request):
                return ajax_success_response(message='Message archivé.', code="message_archived")
            messages.success(request, 'Message archivé.')
            return redirect('read_message', pk=pk)
        if action == 'assign_me':
            msg = assign_message_to_user(message=msg, user=request.user)
            if is_ajax(request):
                return ajax_success_response(message='Message assigné.', code="message_assigned")
            messages.success(request, 'Message assigné.')
            return redirect('read_message', pk=pk)
        if action == 'unassign':
            msg = unassign_message(msg)
            if is_ajax(request):
                return ajax_success_response(message='Assignation retirée.', code="message_unassigned")
            messages.success(request, "Assignation retirée.")
            return redirect('read_message', pk=pk)
        if action == 'respond':
            reply_form = ContactMessageReplyForm(request.POST)
            if reply_form.is_valid():
                response_result = respond_to_message(actor=request.user, message=msg, reply_form=reply_form)
                msg = response_result.message
                if is_ajax(request):
                    return ajax_success_response(message='Réponse enregistrée.', code="message_responded")
                messages.success(request, 'Réponse enregistrée.')
                return redirect('read_message', pk=pk)
            if is_ajax(request):
                return ajax_form_error_response(reply_form)
        else:
            if is_ajax(request):
                return ajax_error_response(message='Action invalide.', code="invalid_action", http_status=400)
            messages.error(request, "Action invalide.")
            return redirect('read_message', pk=pk)
    return render(request, 'admin_dashboard/read_message.html', {
        'church': church,
        'msg': msg,
        'reply_form': reply_form,
        'replies': msg.replies.select_related('created_by'),
    })
