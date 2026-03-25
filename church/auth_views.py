"""Authentication-oriented views and login helpers for the church app."""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.urls import reverse

from .rate_limits import build_login_rate_limit_rules, build_rate_limit_message, consume_rate_limits, reset_rate_limits
from .tenancy import get_accessible_churches
from .church_context import _has_pending_invitations


class TenantLoginView(LoginView):
    """Apply tenant-aware login throttling and post-login routing."""

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
        """Route the user to the right tenant landing page after login."""
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
