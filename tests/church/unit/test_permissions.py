from church.models import ChurchMembership
from church.permissions import (
    ALL_CAPABILITIES,
    CAP_MANAGE_EVENTS,
    CAP_MANAGE_MEMBERS,
    CAP_MANAGE_MESSAGES,
    CAP_MANAGE_PAGES,
    CAP_MANAGE_SITE_SETTINGS,
    CAP_VIEW_AUDIT,
    get_capabilities_for_user,
    get_churches_for_capability,
)
from tests.factories import SaaSTestCase


class PermissionUnitTests(SaaSTestCase):
    def test_superuser_gets_all_capabilities(self):
        user = self.create_user(is_superuser=True)

        self.assertEqual(get_capabilities_for_user(user, None), set(ALL_CAPABILITIES))

    def test_admin_role_capabilities_include_audit_and_messages(self):
        user = self.create_user()
        church = self.create_church()
        membership = self.add_membership(user, church, role=ChurchMembership.Role.ADMIN)
        capabilities = get_capabilities_for_user(user, membership)

        self.assertIn(CAP_VIEW_AUDIT, capabilities)
        self.assertIn(CAP_MANAGE_MESSAGES, capabilities)
        self.assertIn(CAP_MANAGE_MEMBERS, capabilities)
        self.assertIn(CAP_MANAGE_PAGES, capabilities)
        self.assertNotIn(CAP_MANAGE_SITE_SETTINGS, capabilities)

    def test_staff_role_is_limited_to_content_and_member_management(self):
        user = self.create_user()
        church = self.create_church()
        membership = self.add_membership(user, church, role=ChurchMembership.Role.STAFF)
        capabilities = get_capabilities_for_user(user, membership)

        self.assertIn(CAP_MANAGE_EVENTS, capabilities)
        self.assertIn(CAP_MANAGE_PAGES, capabilities)
        self.assertIn(CAP_MANAGE_MEMBERS, capabilities)
        self.assertNotIn(CAP_MANAGE_MESSAGES, capabilities)

    def test_secretary_role_can_manage_messages_and_members(self):
        user = self.create_user()
        church = self.create_church()
        membership = self.add_membership(user, church, role=ChurchMembership.Role.SECRETARY)
        capabilities = get_capabilities_for_user(user, membership)

        self.assertIn(CAP_MANAGE_MESSAGES, capabilities)
        self.assertIn(CAP_MANAGE_MEMBERS, capabilities)
        self.assertNotIn(CAP_MANAGE_PAGES, capabilities)

    def test_capability_resolution_excludes_suspended_and_archived_churches(self):
        user = self.create_user()
        active_church = self.create_church(name="Active Church")
        suspended_church = self.create_church(
            name="Suspended Church",
            status="suspended",
        )
        archived_church = self.create_church(
            name="Archived Church",
            status="archived",
        )

        self.add_membership(user, active_church, role=ChurchMembership.Role.STAFF)
        ChurchMembership.objects.bulk_create(
            [
                ChurchMembership(
                    user=user,
                    church=suspended_church,
                    role=ChurchMembership.Role.STAFF,
                    is_active=True,
                ),
                ChurchMembership(
                    user=user,
                    church=archived_church,
                    role=ChurchMembership.Role.STAFF,
                    is_active=True,
                ),
            ]
        )

        churches = list(get_churches_for_capability(user, CAP_MANAGE_MEMBERS))

        self.assertEqual(churches, [active_church])
