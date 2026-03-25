"""Shared helpers for church views."""

from datetime import timedelta
import logging
import sys

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .audit import log_audit
from .background_jobs import enqueue_invite_email_job
from .limits import enforce_limits_for_model
from .membership_policy import get_pending_invitations_for_user
from .models import Church, ChurchInvitation, ChurchMembership, Notification
from .rate_limits import (
    build_login_rate_limit_rules,
    build_rate_limit_message,
    reset_rate_limits,
    consume_rate_limits,
)
from .tenancy import get_accessible_churches, get_membership, get_selected_church


class TenantLoginView(LoginView):
    template_name = "registration/login.html"

    def post(self, request, *args, **kwargs):
        """Apply login throttling before attempting authentication."""
        username = (request.POST.get("username") or "").strip()
        self._login_rate_limit_rules = build_login_rate_limit_rules(request, username)
        throttle_result = consume_rate_limits(self._login_rate_limit_rules)
        if throttle_result.limited:
            form = self.get_form()
            form.add_error(None, build_rate_limit_message(throttle_result.retry_after_seconds))
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Clear login throttle buckets after a successful authentication."""
        if hasattr(self, "_login_rate_limit_rules"):
            reset_rate_limits(self._login_rate_limit_rules)
        return super().form_valid(form)

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
    """Return whether the request was sent through AJAX."""
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


def build_ajax_payload(*, success, message="", code="", data=None, errors=None, redirect=None):
    """Build the shared AJAX response payload used across dashboard and public views."""
    return {
        "status": "success" if success else "error",
        "success": success,
        "message": message,
        "code": code,
        "data": data or {},
        "errors": errors or {},
        "redirect": redirect,
    }


def ajax_response(*, success, message="", code="", data=None, errors=None, redirect=None, http_status=200):
    """Return a JSON response that follows the project-wide AJAX contract."""
    return JsonResponse(
        build_ajax_payload(
            success=success,
            message=message,
            code=code,
            data=data,
            errors=errors,
            redirect=redirect,
        ),
        status=http_status,
    )


def ajax_success_response(*, message="", code="ok", data=None, redirect=None, http_status=200):
    """Return a successful AJAX response with the shared envelope."""
    return ajax_response(
        success=True,
        message=message,
        code=code,
        data=data,
        redirect=redirect,
        http_status=http_status,
    )


def ajax_error_response(*, message="", code="error", data=None, errors=None, redirect=None, http_status=400):
    """Return a failed AJAX response with the shared envelope."""
    return ajax_response(
        success=False,
        message=message,
        code=code,
        data=data,
        errors=errors,
        redirect=redirect,
        http_status=http_status,
    )


def ajax_form_error_response(form, *, message="Veuillez corriger les erreurs du formulaire.", code="validation_error", http_status=400):
    """Return a validation error response using structured form errors."""
    errors = form.errors.get_json_data() if hasattr(form.errors, "get_json_data") else form.errors
    return ajax_error_response(
        message=message,
        code=code,
        errors=errors,
        http_status=http_status,
    )


def _build_invite_url(request, invite):
    return request.build_absolute_uri(reverse('accept_invite', args=[invite.token]))


def _send_invite_email(invite_url, invite):
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


def _enqueue_invite_email_delivery(request, invite):
    """Persist an invitation email job so it can be delivered by a worker."""
    return enqueue_invite_email_job(invite, _build_invite_url(request, invite))


def _send_invite_email(invite_url, invite):
    """Queue invitation delivery through the durable background job store."""
    return enqueue_invite_email_job(invite, invite_url)


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
    """Run a callback after commit without spawning background threads."""
    running_tests = "test" in sys.argv

    def run_callback():
        try:
            callback()
        except Exception:
            if not running_tests:
                logger.error("Failed to execute after-commit callback", exc_info=True)

    if running_tests:
        run_callback()
        return

    transaction.on_commit(run_callback)


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
                    return ajax_form_error_response(form, message="Corrigez les erreurs du formulaire.", code="validation_error")
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
                logger.error(f"Failed to log audit for action {action}", exc_info=True)
            if after_save:
                after_save(obj, is_created)
            if is_ajax(request):
                return ajax_success_response(
                    message=success_message,
                    code=f"{action}_{obj.__class__.__name__.lower()}",
                    redirect=reverse(success_url_name),
                )
            messages.success(request, success_message)
            return redirect(success_url_name)
        if is_ajax(request):
            return ajax_form_error_response(form)
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
            logger.error("Failed to log audit for delete action", exc_info=True)
        obj.delete()
        if is_ajax(request):
            return ajax_success_response(
                message=success_message,
                code=f"delete_{model.__name__.lower()}",
            )
        messages.success(request, success_message)
    return redirect(success_url_name)
