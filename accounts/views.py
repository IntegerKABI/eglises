from django.contrib.auth.views import LoginView
from django.urls import reverse

from church.tenancy import get_accessible_churches


class TenantLoginView(LoginView):
    template_name = "registration/login.html"

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to

        user = self.request.user
        churches = get_accessible_churches(user)
        church_count = churches.count()

        if church_count == 0:
            self.request.session.pop("active_church_id", None)
            return reverse("home")

        active_church_id = self.request.session.get("active_church_id")
        if active_church_id and churches.filter(id=active_church_id).exists():
            return reverse("dashboard")

        if church_count == 1:
            self.request.session["active_church_id"] = churches.values_list("id", flat=True).first()
            return reverse("dashboard")

        self.request.session.pop("active_church_id", None)
        return reverse("select_church")
