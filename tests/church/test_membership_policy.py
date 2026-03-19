from django.core.exceptions import ValidationError
from django.urls import reverse

from church.forms import (
    ChurchInvitationForm,
    ChurchMembershipAssignForm,
    ChurchMembershipUpdateForm,
)
from church.models import ChurchInvitation, ChurchMembership

from .helpers import ChurchTestCase


class SingleChurchMembershipPolicyTests(ChurchTestCase):
    def test_non_superuser_cannot_have_two_active_memberships(self):
        user = self.create_user(username="member", email="member@example.com")
        church_one = self.create_church(name="Alpha Church")
        church_two = self.create_church(name="Beta Church")
        self.add_membership(user, church_one)

        with self.assertRaises(ValidationError):
            self.add_membership(
                user,
                church_two,
                role=ChurchMembership.Role.STAFF,
            )

    def test_invitation_form_rejects_existing_user_from_another_church(self):
        user = self.create_user(username="invited", email="invited@example.com")
        church_one = self.create_church(name="Alpha Church")
        church_two = self.create_church(name="Beta Church")
        self.add_membership(user, church_one)

        form = ChurchInvitationForm(
            data={"email": user.email, "role": ChurchMembership.Role.STAFF},
            church=church_two,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("une seule eglise active", str(form.errors).lower())

    def test_accept_invite_rejects_user_with_other_active_membership(self):
        user = self.create_user(username="accepted", email="accepted@example.com")
        church_one = self.create_church(name="Alpha Church")
        church_two = self.create_church(name="Beta Church")
        self.add_membership(user, church_one)
        invite = ChurchInvitation.objects.create(
            church=church_two,
            email=user.email,
            role=ChurchMembership.Role.STAFF,
            invited_by=user,
        )

        self.client.force_login(user)
        response = self.client.post(reverse("accept_invite", args=[invite.token]))

        self.assertRedirects(
            response,
            reverse("pending_invitations"),
            fetch_redirect_response=False,
        )
        self.assertFalse(
            ChurchMembership.objects.filter(
                user=user,
                church=church_two,
                is_active=True,
            ).exists()
        )
        invite.refresh_from_db()
        self.assertEqual(invite.status, ChurchInvitation.Status.PENDING)


class MembershipWorkflowFormTests(ChurchTestCase):
    def test_assign_form_reactivates_existing_membership(self):
        user = self.create_user(
            username="assign-target",
            email="assign-target@example.com",
        )
        church = self.create_church(name="Assign Church")
        membership = self.add_membership(
            user,
            church,
            role=ChurchMembership.Role.STAFF,
            is_active=False,
        )

        form = ChurchMembershipAssignForm(
            data={
                "identifier": user.username,
                "role": ChurchMembership.Role.SECRETARY,
            },
            church=church,
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved_membership = form.save(church)

        membership.refresh_from_db()
        self.assertEqual(saved_membership.pk, membership.pk)
        self.assertEqual(saved_membership.role, ChurchMembership.Role.SECRETARY)
        self.assertTrue(saved_membership.is_active)

    def test_update_form_rejects_removing_last_active_admin(self):
        admin_user = self.create_user(
            username="last-admin",
            email="last-admin@example.com",
        )
        church = self.create_church(name="Admin Church")
        membership = self.add_membership(
            admin_user,
            church,
            role=ChurchMembership.Role.ADMIN,
        )

        form = ChurchMembershipUpdateForm(
            data={"role": ChurchMembership.Role.STAFF, "is_active": True},
            instance=membership,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("au moins un administrateur actif", str(form.errors).lower())

