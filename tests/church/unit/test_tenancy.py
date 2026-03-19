from church.models import Church, ChurchMembership
from church.tenancy import get_accessible_churches, get_membership, get_selected_church
from tests.factories import SaaSTestCase


class TenancyUnitTests(SaaSTestCase):
    def test_get_accessible_churches_excludes_suspended_and_archived(self):
        user = self.create_user(username="tenant-user", email="tenant-user@example.com")
        active = self.create_church(name="Active Church", status=Church.Status.ACTIVE)
        draft = self.create_church(name="Draft Church", status=Church.Status.DRAFT)
        suspended = self.create_church(name="Suspended Church", status=Church.Status.SUSPENDED)
        archived = self.create_church(name="Archived Church", status=Church.Status.ARCHIVED)
        self.add_membership(user, active)
        self.add_membership(user, draft, role=ChurchMembership.Role.STAFF, is_active=False)
        ChurchMembership.objects.filter(user=user, church=draft).update(is_active=True)
        self.add_membership(user, suspended, role=ChurchMembership.Role.STAFF, is_active=False)
        ChurchMembership.objects.filter(user=user, church=suspended).update(is_active=True)
        self.add_membership(user, archived, role=ChurchMembership.Role.STAFF, is_active=False)
        ChurchMembership.objects.filter(user=user, church=archived).update(is_active=True)

        churches = list(get_accessible_churches(user))

        self.assertEqual(churches, [active, draft])

    def test_get_selected_church_sets_session_for_single_membership(self):
        user = self.create_user(username="selected-user", email="selected-user@example.com")
        church = self.create_church(name="Selected Church")
        self.add_membership(user, church)
        request = self.client.request().wsgi_request
        request.user = user
        request.session = self.client.session

        selected = get_selected_church(request)

        self.assertEqual(selected, church)
        self.assertEqual(request.session.get("active_church_id"), church.id)

    def test_get_membership_returns_only_active_membership(self):
        user = self.create_user(username="inactive-user", email="inactive-user@example.com")
        church = self.create_church(name="Membership Church")
        self.add_membership(user, church, is_active=False)

        membership = get_membership(user, church)

        self.assertIsNone(membership)

