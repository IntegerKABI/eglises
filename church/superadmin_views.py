"""Superadmin tenant management views."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .audit import log_audit
from .forms import (
    SuperAdminChurchCreateForm,
    SuperAdminChurchPlanForm,
    SuperAdminChurchStatusForm,
    SuperAdminChurchUpdateForm,
)
from .limits import get_plan_usage
from .models import AuditLog, Church, ChurchMembership
from .permissions import CAP_MANAGE_SITE_SETTINGS, require_capability
from .view_helpers import _querystring_without_page, _schedule_safe_after_commit, is_ajax


def _superadmin_church_queryset():
    admin_memberships = ChurchMembership.objects.filter(
        role=ChurchMembership.Role.ADMIN,
        is_active=True,
    ).select_related('user')
    return (
        Church.objects.all()
        .prefetch_related(
            Prefetch('memberships', queryset=admin_memberships, to_attr='active_admin_memberships')
        )
        .annotate(
            active_admin_count=Count(
                'memberships',
                filter=Q(
                    memberships__role=ChurchMembership.Role.ADMIN,
                    memberships__is_active=True,
                ),
                distinct=True,
            )
        )
        .order_by('name', 'id')
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


def _audit_superadmin_church_action(*, actor, church, action, metadata=None):
    try:
        log_audit(
            actor=actor,
            church=church,
            action=action,
            instance=church,
            metadata=metadata or {},
        )
    except Exception:
        pass


@login_required
@require_capability(CAP_MANAGE_SITE_SETTINGS)
def superadmin_church_list(request):
    churches = _superadmin_church_queryset()

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

    paginator = Paginator(churches, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    tenant_cards = [
        {
            'church': church,
            'usage': get_plan_usage(church),
        }
        for church in page_obj.object_list
    ]

    return render(
        request,
        'admin_dashboard/superadmin/church_list.html',
        {
            'church': getattr(request, 'current_church', None),
            'churches': page_obj,
            'page_obj': page_obj,
            'tenant_cards': tenant_cards,
            'querystring': _querystring_without_page(request),
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
    church = get_object_or_404(_superadmin_church_queryset(), pk=pk)
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
    if request.method == 'POST':
        form = SuperAdminChurchCreateForm(request.POST, request.FILES)
        if form.is_valid():
            church = form.save()

            def after_commit():
                _audit_superadmin_church_action(
                    actor=request.user,
                    church=church,
                    action='tenant_create',
                    metadata={
                        'status': church.status,
                        'plan': church.plan,
                    },
                )
                try:
                    log_audit(
                        actor=request.user,
                        church=church,
                        action='tenant_assign_admin',
                        instance=form.created_membership,
                        metadata={
                            'user_id': form.created_admin_user.pk,
                            'username': form.created_admin_user.username,
                        },
                    )
                except Exception:
                    pass

            _schedule_safe_after_commit(after_commit)

            if is_ajax(request):
                return JsonResponse(
                    {
                        'success': True,
                        'message': "Eglise creee avec son premier administrateur.",
                        'redirect': reverse('superadmin_church_detail', args=[church.pk]),
                    }
                )
            messages.success(request, "Eglise creee avec son premier administrateur.")
            return redirect('superadmin_church_detail', pk=church.pk)
        if is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
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
    managed_church = get_object_or_404(Church, pk=pk)
    if request.method == 'POST':
        form = SuperAdminChurchUpdateForm(request.POST, request.FILES, instance=managed_church)
        if form.is_valid():
            church = form.save()

            _schedule_safe_after_commit(
                lambda: _audit_superadmin_church_action(
                    actor=request.user,
                    church=church,
                    action='tenant_update',
                    metadata={'section': 'profile'},
                )
            )

            if is_ajax(request):
                return JsonResponse(
                    {
                        'success': True,
                        'message': "Profil de l'eglise mis a jour.",
                        'redirect': reverse('superadmin_church_detail', args=[church.pk]),
                    }
                )
            messages.success(request, "Profil de l'eglise mis a jour.")
            return redirect('superadmin_church_detail', pk=church.pk)
        if is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
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
    managed_church = get_object_or_404(Church, pk=pk)
    previous_status = managed_church.status
    if request.method == 'POST':
        form = SuperAdminChurchStatusForm(request.POST, instance=managed_church)
        if form.is_valid():
            church = form.save()

            _schedule_safe_after_commit(
                lambda: _audit_superadmin_church_action(
                    actor=request.user,
                    church=church,
                    action='tenant_status_update',
                    metadata={
                        'previous_status': previous_status,
                        'new_status': church.status,
                    },
                )
            )

            if is_ajax(request):
                return JsonResponse(
                    {
                        'success': True,
                        'message': "Statut de l'eglise mis a jour.",
                        'redirect': reverse('superadmin_church_detail', args=[church.pk]),
                    }
                )
            messages.success(request, "Statut de l'eglise mis a jour.")
            return redirect('superadmin_church_detail', pk=church.pk)
        if is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
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
    managed_church = get_object_or_404(Church, pk=pk)
    before_limits = _serialize_limit_configuration(managed_church)
    if request.method == 'POST':
        form = SuperAdminChurchPlanForm(request.POST, instance=managed_church)
        if form.is_valid():
            church = form.save()
            after_limits = _serialize_limit_configuration(church)

            _schedule_safe_after_commit(
                lambda: _audit_superadmin_church_action(
                    actor=request.user,
                    church=church,
                    action='tenant_plan_update',
                    metadata={
                        'previous_plan': before_limits,
                        'current_plan': after_limits,
                    },
                )
            )

            if is_ajax(request):
                return JsonResponse(
                    {
                        'success': True,
                        'message': "Plan et limites mis a jour.",
                        'redirect': reverse('superadmin_church_detail', args=[church.pk]),
                    }
                )
            messages.success(request, "Plan et limites mis a jour.")
            return redirect('superadmin_church_detail', pk=church.pk)
        if is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
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
    managed_church = get_object_or_404(Church, pk=pk)
    if request.method != 'POST':
        return redirect('superadmin_church_detail', pk=managed_church.pk)

    request.session['active_church_id'] = managed_church.pk
    messages.success(request, f"Contexte bascule sur {managed_church.name}.")
    return redirect('dashboard')

