from django.urls import reverse

from church.models import ChurchInvitation, ChurchMembership
from church.permissions import (
    CAP_MANAGE_EVENTS,
    CAP_SWITCH_CHURCH,
    CAP_VIEW_AUDIT,
    get_churches_for_capability,
    user_has_any_capability,
)

from .helpers import ChurchTestCase


class CapabilityConsistencyTests(ChurchTestCase):
    def setUp(self):
        super().setUp()
        self.admin_user = self.create_user(
            username="audit-admin",
            email="audit-admin@example.com",
        )
        self.staff_user = self.create_user(
            username="audit-staff",
            email="audit-staff@example.com",
        )
        self.superuser = self.create_user(
            username="platform-root",
            email="root@example.com",
            is_superuser=True,
        )
        self.church_one = self.create_church(name="Audit Church")
        self.church_two = self.create_church(name="Second Audit Church")
        self.add_membership(self.admin_user, self.church_one, role=ChurchMembership.Role.ADMIN)
        self.add_membership(self.staff_user, self.church_one, role=ChurchMembership.Role.STAFF)

    def test_admin_capability_helpers_match_audit_access(self):
        self.assertTrue(user_has_any_capability(self.admin_user, CAP_VIEW_AUDIT))
        self.assertEqual(
            list(get_churches_for_capability(self.admin_user, CAP_VIEW_AUDIT)),
            [self.church_one],
        )

    def test_staff_cannot_view_audit_but_keeps_role_capabilities(self):
        self.assertFalse(user_has_any_capability(self.staff_user, CAP_VIEW_AUDIT))
        self.assertTrue(user_has_any_capability(self.staff_user, CAP_MANAGE_EVENTS))
        self.assertFalse(
            get_churches_for_capability(self.staff_user, CAP_VIEW_AUDIT).exists()
        )

    def test_superuser_switch_church_and_audit_helpers_share_same_source(self):
        self.assertTrue(user_has_any_capability(self.superuser, CAP_VIEW_AUDIT))
        self.assertTrue(user_has_any_capability(self.superuser, CAP_SWITCH_CHURCH))

    def test_audit_route_denies_staff_and_allows_admin(self):
        self.login_to_church(self.staff_user, self.church_one)
        staff_response = self.client.get(reverse("manage_audit_logs"))
        self.assertRedirects(
            staff_response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )

        self.login_to_church(self.admin_user, self.church_one)
        admin_response = self.client.get(reverse("manage_audit_logs"))
        self.assertEqual(admin_response.status_code, 200)

    def test_dashboard_redirects_user_with_pending_invitation_when_no_church_selected(self):
        user = self.create_user(username="pending-access", email="pending-access@example.com")
        ChurchInvitation.objects.create(
            church=self.church_two,
            email=user.email,
            role=ChurchMembership.Role.STAFF,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response,
            reverse("pending_invitations"),
            fetch_redirect_response=False,
        )

