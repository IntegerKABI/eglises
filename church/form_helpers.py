"""Church-scoped form orchestration helpers for dashboard views."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

from .audit import log_audit_safely
from .church_context import _require_church
from .limits import enforce_limits_for_model
from .http_helpers import ajax_form_error_response, ajax_success_response, is_ajax


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
    """Create or update a church-scoped object and keep the view layer thin."""
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
            action = "create" if is_created else "update"
            log_audit_safely(
                actor=request.user,
                church=church if hasattr(obj, 'church_id') else None,
                action=action,
                instance=obj,
                metadata={"form": form.__class__.__name__},
                error_message=f"Failed to log audit for action {action}",
            )
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
    """Delete a church-scoped object without duplicating request handling in views."""
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    obj = get_object_or_404(model, pk=pk, church=church)
    if request.method == 'POST':
        if after_delete:
            after_delete(obj)
        log_audit_safely(
            actor=request.user,
            church=church,
            action="delete",
            instance=obj,
            error_message="Failed to log audit for delete action",
        )
        obj.delete()
        if is_ajax(request):
            return ajax_success_response(
                message=success_message,
                code=f"delete_{model.__name__.lower()}",
            )
        messages.success(request, success_message)
    return redirect(success_url_name)
