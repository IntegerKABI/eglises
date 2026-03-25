"""Notification, audit, and platform settings views."""

from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .audit import log_audit_safely
from .forms import SiteSettingsForm
from .limits import filter_notifications_for_retention
from .models import AuditLog, Notification, SiteSettings
from .permissions import CAP_MANAGE_SITE_SETTINGS, CAP_VIEW_AUDIT, CAP_VIEW_DASHBOARD, get_churches_for_capability, require_capability
from .tenancy import get_accessible_churches, get_selected_church
from .view_helpers import (
    _get_choice_param,
    _get_text_param,
    _querystring_without_page,
    _require_church,
    ajax_form_error_response,
    ajax_success_response,
    is_ajax,
)


@login_required
@require_capability(CAP_VIEW_DASHBOARD)
def manage_notifications(request):
    """Show the user's notifications for the active church context."""
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
    """Open a notification and redirect to its linked destination when valid."""
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
def mark_all_notifications_read(request):
    """Mark all visible notifications as read for the active church context."""
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
    """Show audit logs so platform and tenant admins can review activity."""
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


@login_required
@require_capability(CAP_MANAGE_SITE_SETTINGS)
def site_settings(request):
    """Manage global platform settings."""
    settings_obj = SiteSettings.get()
    church = get_selected_church(request)

    if request.method == 'POST':
        form = SiteSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            form.save()
            log_audit_safely(
                actor=request.user,
                church=None,
                action="settings_update",
                instance=settings_obj,
                metadata={"section": "site_settings"},
                error_message="Failed to log site settings update action",
            )
            if is_ajax(request):
                return ajax_success_response(
                    message='Paramètres de la plateforme mis à jour !',
                    code="site_settings_updated",
                )
            messages.success(request, 'Paramètres de la plateforme mis à jour !')
            return redirect('site_settings')
        elif is_ajax(request):
            return ajax_form_error_response(form)
    else:
        form = SiteSettingsForm(instance=settings_obj)

    return render(request, 'admin_dashboard/site_settings.html', {
        'church': church,
        'form': form,
        'site_settings': settings_obj,
    })
