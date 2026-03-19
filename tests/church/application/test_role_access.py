from django.urls import reverse

from church.models import ChurchMembership
from tests.factories import SaaSTestCase


class RoleAccessApplicationTests(SaaSTestCase):
    admin_routes = [
        "dashboard",
        "manage_events",
        "manage_sermons",
        "manage_members",
        "manage_pages",
        "manage_messages",
        "manage_users",
        "manage_audit_logs",
    ]
    staff_routes = [
        "dashboard",
        "manage_events",
        "manage_sermons",
        "manage_pages",
    ]
    secretary_routes = [
        "dashboard",
        "manage_events",
        "manage_sermons",
        "manage_messages",
        "manage_members",
    ]

    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="route-admin")
        self.staff = self.create_user(username="route-staff")
        self.secretary = self.create_user(username="route-secretary")
        self.superuser = self.create_user(username="route-super", is_superuser=True)
        self.church = self.create_church(name="Route Church")
        self.other_church = self.create_church(name="Other Route Church")
        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)
        self.add_membership(self.staff, self.church, role=ChurchMembership.Role.STAFF)
        self.add_membership(self.secretary, self.church, role=ChurchMembership.Role.SECRETARY)
        self.event = self.create_event(self.other_church, title="Outside event")

    def _assert_routes_accessible(self, user, route_names):
        self.login_to_church(user, self.church)
        for route_name in route_names:
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200, route_name)

    def test_admin_route_matrix(self):
        self._assert_routes_accessible(self.admin, self.admin_routes)

    def test_staff_route_matrix(self):
        self._assert_routes_accessible(self.staff, self.staff_routes)
        response = self.client.get(reverse("manage_messages"))
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        response = self.client.get(reverse("manage_members"))
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_secretary_route_matrix(self):
        self._assert_routes_accessible(self.secretary, self.secretary_routes)
        response = self.client.get(reverse("manage_pages"))
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_superadmin_can_access_platform_settings(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("site_settings"))
        self.assertEqual(response.status_code, 200)

    def test_tenant_isolation_blocks_editing_objects_from_another_church(self):
        self.login_to_church(self.admin, self.church)
        response = self.client.get(reverse("edit_event", args=[self.event.pk]))
        self.assertEqual(response.status_code, 404)

