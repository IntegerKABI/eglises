"""Superadmin tenant management views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from ..forms import (
    SuperAdminChurchCreateForm,
    SuperAdminChurchPlanForm,
    SuperAdminChurchStatusForm,
    SuperAdminChurchUpdateForm,
)
from ..limits import get_plan_usage, get_plan_usage_for_churches
from ..models import AuditLog, Church, ChurchInvitation, ChurchMembership, Event, Member, Page, Sermon
from ..permissions import CAP_MANAGE_SITE_SETTINGS, require_capability
from ..rate_limits import (
    build_invite_send_rate_limit_rules,
    build_rate_limit_message,
    consume_rate_limits,
)
from ..services.superadmin import (
    create_church_from_form,
    update_church_plan_from_form,
    update_church_profile_from_form,
    update_church_status_from_form,
)
from ..helpers.list_view import build_paginated_list_context
from ..helpers.http import ajax_form_error_response, ajax_success_response, is_ajax


def _superadmin_church_list_queryset():
    admin_memberships = ChurchMembership.objects.filter(
        role=ChurchMembership.Role.ADMIN,
        is_active=True,
    ).select_related('user').order_by('user__first_name', 'user__last_name', 'user__username')
    storage_events = Event.objects.only('church_id', 'image').order_by('id')
    storage_sermons = Sermon.objects.only('church_id', 'image').order_by('id')
    storage_members = Member.objects.only('church_id', 'photo').order_by('id')
    storage_pages = Page.objects.only('church_id', 'image').order_by('id')
    return (
        Church.objects.all()
        .prefetch_related(
            Prefetch('memberships', queryset=admin_memberships, to_attr='active_admin_memberships'),
            Prefetch('events', queryset=storage_events, to_attr='_prefetched_storage_events'),
            Prefetch('sermons', queryset=storage_sermons, to_attr='_prefetched_storage_sermons'),
            Prefetch('members', queryset=storage_members, to_attr='_prefetched_storage_members'),
            Prefetch('pages', queryset=storage_pages, to_attr='_prefetched_storage_pages'),
        )
        .annotate(
            active_admin_count=Count(
                'memberships',
                filter=Q(
                    memberships__role=ChurchMembership.Role.ADMIN,
                    memberships__is_active=True,
                ),
                distinct=True,
            ),
            usage_members_count=Count('members', distinct=True),
            usage_events_count=Count('events', distinct=True),
            usage_sermons_count=Count('sermons', distinct=True),
            usage_pages_count=Count('pages', distinct=True),
            usage_users_count=Count(
                'memberships',
                filter=Q(memberships__is_active=True),
                distinct=True,
            ),
            usage_pending_invitations_count=Count(
                'invitations',
                filter=Q(
                    invitations__status=ChurchInvitation.Status.PENDING,
                    invitations__expires_at__gt=timezone.now(),
                ),
                distinct=True,
            ),
        )
        .order_by('name', 'id')
    )


def _superadmin_church_detail_queryset():
    admin_memberships = ChurchMembership.objects.filter(
        role=ChurchMembership.Role.ADMIN,
        is_active=True,
    ).select_related('user').order_by('user__first_name', 'user__last_name', 'user__username')
    return Church.objects.all().prefetch_related(
        Prefetch('memberships', queryset=admin_memberships, to_attr='active_admin_memberships')
    )


def _serialize_limit_configuration(church):
    resources = (
        'members',
        'events',
        'sermons',
        'pages',
        'users',
        'pending_invitations',
        'storage_mb',
        'message_retention_days',
        'notification_retention_days',
    )
    return {resource: church.get_plan_limit(resource) for resource in resources}


def _build_effective_limit_rows(church):
    labels = {
        'members': 'Membres',
        'events': 'Evenements',
        'sermons': 'Predications',
        'pages': 'Pages',
        'users': 'Utilisateurs',
        'pending_invitations': 'Invitations en attente',
        'storage_mb': 'Stockage (Mo)',
        'message_retention_days': 'Retention messages (jours)',
        'notification_retention_days': 'Retention notifications (jours)',
    }
    rows = []
    for key, label in labels.items():
        value = church.get_plan_limit(key)
        rows.append(
            {
                'key': key,
                'label': label,
                'value': value,
                'display_value': "Illimite" if value is None else value,
            }
        )
    return rows


@login_required
@require_capability(CAP_MANAGE_SITE_SETTINGS)
def superadmin_church_list(request):
    """Render the tenant list so platform admins can inspect all churches."""
    churches = _superadmin_church_list_queryset()

    query = (request.GET.get('q') or '').strip()
    if query:
        churches = churches.filter(
            Q(name__icontains=query)
            | Q(city__icontains=query)
            | Q(slug__icontains=query)
            | Q(email__icontains=query)
            | Q(
                memberships__user__email__icontains=query,
                memberships__role=ChurchMembership.Role.ADMIN,
                memberships__is_active=True,
            )
        ).distinct()

    status = request.GET.get('status')
    allowed_statuses = {choice for choice, _ in Church.Status.choices}
    if status in allowed_statuses:
        churches = churches.filter(status=status)
    else:
        status = ''

    plan = request.GET.get('plan')
    allowed_plans = {choice for choice, _ in Church.Plan.choices}
    if plan in allowed_plans:
        churches = churches.filter(plan=plan)
    else:
        plan = ''

    context = build_paginated_list_context(request=request, queryset=churches, per_page=12, item_key='churches')
    page_obj = context['page_obj']
    usage_by_church = get_plan_usage_for_churches(page_obj.object_list)

    tenant_cards = [
        {
            'church': church,
            'usage': usage_by_church[church.pk],
        }
        for church in page_obj.object_list
    ]

    return render(
        request,
        'admin_dashboard/superadmin/church_list.html',
        {
            'church': getattr(request, 'current_church', None),
            **context,
            'tenant_cards': tenant_cards,
            'status_choices': Church.Status.choices,
            'plan_choices': Church.Plan.choices,
            'selected_status': status,
            'selected_plan': plan,
            'search_query': query,
        },
    )


@login_required
@require_capability(CAP_MANAGE_SITE_SETTINGS)
def superadmin_church_detail(request, pk):
    """Show tenant details, usage, and recent activity for platform admins."""
    church = get_object_or_404(_superadmin_church_detail_queryset(), pk=pk)
    tenant_usage = get_plan_usage(church)
    recent_audit_logs = AuditLog.objects.filter(church=church).select_related('actor')[:10]

    return render(
        request,
        'admin_dashboard/superadmin/church_detail.html',
        {
            'church': getattr(request, 'current_church', None),
            'managed_church': church,
            'tenant_usage': tenant_usage,
            'effective_limits': _build_effective_limit_rows(church),
            'recent_audit_logs': recent_audit_logs,
            'active_admin_memberships': getattr(church, 'active_admin_memberships', []),
        },
    )


@login_required
@require_capability(CAP_MANAGE_SITE_SETTINGS)
def superadmin_church_create(request):
    """Create a tenant and its first administrator from the platform console."""
    if request.method == 'POST':
        form = SuperAdminChurchCreateForm(request.POST, request.FILES)
        if request.POST.get("admin_assignment_mode") == "existing":
            throttle_result = consume_rate_limits(
                build_invite_send_rate_limit_rules(request, request.user, "platform")
            )
            if throttle_result.limited:
                message = build_rate_limit_message(throttle_result.retry_after_seconds)
                form.add_error(None, message)
                if is_ajax(request):
                    return ajax_form_error_response(form, message=message, code="rate_limited", http_status=429)
                return render(
                    request,
                    'admin_dashboard/superadmin/church_form.html',
                    {
                        'church': getattr(request, 'current_church', None),
                        'form': form,
                        'title': "Creer une eglise",
                        'mode': 'create',
                    },
                )
        if form.is_valid():
            result = create_church_from_form(request=request, actor=request.user, form=form)
            church = result.church
            success_message = result.success_message

            if is_ajax(request):
                return ajax_success_response(
                    message=success_message,
                    code="tenant_created",
                    redirect=reverse('superadmin_church_detail', args=[church.pk]),
                )
            messages.success(request, success_message)
            return redirect('superadmin_church_detail', pk=church.pk)
        if is_ajax(request):
            return ajax_form_error_response(form)
    else:
        form = SuperAdminChurchCreateForm()

    return render(
        request,
        'admin_dashboard/superadmin/church_form.html',
        {
            'church': getattr(request, 'current_church', None),
            'form': form,
            'title': "Creer une eglise",
            'submit_label': "Creer l'eglise",
            'managed_church': None,
        },
    )


@login_required
@require_capability(CAP_MANAGE_SITE_SETTINGS)
def superadmin_church_edit(request, pk):
    """Edit tenant branding and contact details from the platform console."""
    managed_church = get_object_or_404(Church, pk=pk)
    if request.method == 'POST':
        form = SuperAdminChurchUpdateForm(request.POST, request.FILES, instance=managed_church)
        if form.is_valid():
            church = update_church_profile_from_form(actor=request.user, form=form)

            if is_ajax(request):
                return ajax_success_response(
                    message="Profil de l'église mis à jour.",
                    code="tenant_profile_updated",
                    redirect=reverse('superadmin_church_detail', args=[church.pk]),
                )
            messages.success(request, "Profil de l'église mis à jour.")
            return redirect('superadmin_church_detail', pk=church.pk)
        if is_ajax(request):
            return ajax_form_error_response(form)
    else:
        form = SuperAdminChurchUpdateForm(instance=managed_church)

    return render(
        request,
        'admin_dashboard/superadmin/church_form.html',
        {
            'church': getattr(request, 'current_church', None),
            'form': form,
            'title': f"Modifier {managed_church.name}",
            'submit_label': "Enregistrer les changements",
            'managed_church': managed_church,
        },
    )


@login_required
@require_capability(CAP_MANAGE_SITE_SETTINGS)
def superadmin_church_status(request, pk):
    """Change a tenant's activation state while enforcing admin invariants."""
    managed_church = get_object_or_404(Church, pk=pk)
    previous_status = managed_church.status
    if request.method == 'POST':
        form = SuperAdminChurchStatusForm(request.POST, instance=managed_church)
        if form.is_valid():
            church = update_church_status_from_form(
                actor=request.user,
                form=form,
                previous_status=previous_status,
            )

            if is_ajax(request):
                return ajax_success_response(
                    message="Statut de l'église mis à jour.",
                    code="tenant_status_updated",
                    redirect=reverse('superadmin_church_detail', args=[church.pk]),
                )
            messages.success(request, "Statut de l'église mis à jour.")
            return redirect('superadmin_church_detail', pk=church.pk)
        if is_ajax(request):
            return ajax_form_error_response(form)
    else:
        form = SuperAdminChurchStatusForm(instance=managed_church)

    return render(
        request,
        'admin_dashboard/superadmin/church_status_form.html',
        {
            'church': getattr(request, 'current_church', None),
            'form': form,
            'managed_church': managed_church,
        },
    )


@login_required
@require_capability(CAP_MANAGE_SITE_SETTINGS)
def superadmin_church_plan(request, pk):
    """Update the tenant plan and limit configuration from the platform console."""
    managed_church = get_object_or_404(Church, pk=pk)
    before_limits = _serialize_limit_configuration(managed_church)
    if request.method == 'POST':
        form = SuperAdminChurchPlanForm(request.POST, instance=managed_church)
        if form.is_valid():
            church = update_church_plan_from_form(
                actor=request.user,
                form=form,
                previous_limits=before_limits,
            )

            if is_ajax(request):
                return ajax_success_response(
                    message="Plan et limites mis à jour.",
                    code="tenant_plan_updated",
                    redirect=reverse('superadmin_church_detail', args=[church.pk]),
                )
            messages.success(request, "Plan et limites mis à jour.")
            return redirect('superadmin_church_detail', pk=church.pk)
        if is_ajax(request):
            return ajax_form_error_response(form)
    else:
        form = SuperAdminChurchPlanForm(instance=managed_church)

    return render(
        request,
        'admin_dashboard/superadmin/church_plan_form.html',
        {
            'church': getattr(request, 'current_church', None),
            'form': form,
            'managed_church': managed_church,
            'tenant_usage': get_plan_usage(managed_church),
        },
    )


@login_required
@require_capability(CAP_MANAGE_SITE_SETTINGS)
def superadmin_switch_church(request, pk):
    """Switch the active dashboard context to a managed tenant for support work."""
    managed_church = get_object_or_404(Church, pk=pk)
    if request.method != 'POST':
        return redirect('superadmin_church_detail', pk=managed_church.pk)

    request.session['active_church_id'] = managed_church.pk
    messages.success(request, f"Contexte bascule sur {managed_church.name}.")
    return redirect('dashboard')
