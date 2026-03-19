from django.urls import reverse

from church.models import ChurchMembership
from tests.factories import SaaSTestCase


class DashboardOverviewIntegrationTests(SaaSTestCase):
    def setUp(self):
        super().setUp()
        self.church = self.create_church(name="Eglise Tableau de bord")

        self.admin = self.create_user(username="overview-admin")
        self.staff = self.create_user(username="overview-staff")
        self.secretary = self.create_user(username="overview-secretary")
        self.superuser = self.create_user(username="overview-super", is_superuser=True)

        self.add_membership(self.admin, self.church, role=ChurchMembership.Role.ADMIN)
        self.add_membership(self.staff, self.church, role=ChurchMembership.Role.STAFF)
        self.add_membership(self.secretary, self.church, role=ChurchMembership.Role.SECRETARY)

        self.create_event(self.church, title="Veille de priere")
        self.create_sermon(self.church, title="La fidelite de Dieu")
        self.create_page(self.church, title="Notre vision")
        self.create_member(
            self.church,
            first_name="Grace",
            last_name="Ilunga",
            directory_consent=True,
            directory_consent_source="Fiche d'inscription",
        )
        self.create_message(
            self.church,
            sender_name="Jean Mukendi",
            subject="Demande de priere",
        )

    def _get_dashboard(self, user):
        self.login_to_church(user, self.church)
        return self.client.get(reverse("dashboard"))

    def test_admin_dashboard_shows_plan_section(self):
        response = self._get_dashboard(self.admin)

        self.assertContains(response, "Plan et limites")
        self.assertContains(response, "Messages recents")
        self.assertContains(response, "Membres actifs")
        self.assertContains(response, "Forfait")

    def test_staff_dashboard_is_content_focused(self):
        response = self._get_dashboard(self.staff)

        self.assertNotContains(response, "Plan et limites")
        self.assertContains(response, "Suivi du contenu")
        self.assertContains(response, "Pages actives")
        self.assertNotContains(response, "Messages recents")
        self.assertNotContains(response, "Membres recents")

    def test_secretary_dashboard_is_operations_focused(self):
        response = self._get_dashboard(self.secretary)

        self.assertNotContains(response, "Plan et limites")
        self.assertContains(response, "Messages recents")
        self.assertContains(response, "Membres recents")
        self.assertContains(response, "Assignes a moi")
        self.assertNotContains(response, "Suivi du contenu")

    def test_superuser_dashboard_keeps_plan_section(self):
        response = self._get_dashboard(self.superuser)

        self.assertContains(response, "Plan et limites")
        self.assertContains(response, "Messages recents")
