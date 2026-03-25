"""HTTP and request parameter helpers used by church views."""

from django.http import JsonResponse


def is_ajax(request):
    """Return whether the request was sent through AJAX."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _querystring_without_page(request):
    """Return the current query string without the pagination parameter."""
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


def _parse_bool_param(value):
    """Parse a request parameter into a boolean when the value is explicit."""
    if value in ('1', 'true', 'yes', 'on'):
        return True
    if value in ('0', 'false', 'no', 'off'):
        return False
    return None


def _get_text_param(request, key, max_len=200):
    """Read and clamp a text query parameter."""
    value = request.GET.get(key, '')
    if value is None:
        return ''
    value = value.strip()
    if len(value) > max_len:
        value = value[:max_len]
    return value


def _get_choice_param(request, key, allowed):
    """Read a query parameter and keep it only when it matches an allowed value."""
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
