from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from church.forms import (
    ChurchInvitationForm,
    ChurchMembershipAssignForm,
    ChurchUserCreateForm,
    EventForm,
    InviteSignupForm,
)
from church.models import ChurchMembership
from tests.factories import SaaSTestCase


class ChurchFormTests(SaaSTestCase):
    def test_event_form_rejects_end_date_before_start_date(self):
        form = EventForm(
            data={
                "title": "Retraite",
                "event_date": "2026-04-10",
                "end_date": "2026-04-09",
                "visibility": "public",
                "is_active": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_church_user_create_form_rejects_mismatched_passwords(self):
        form = ChurchUserCreateForm(
            data={
                "username": "new-user",
                "email": "new-user@example.com",
                "role": ChurchMembership.Role.STAFF,
                "password1": "StrongPass123!",
                "password2": "DifferentPass123!",
                "is_active": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("mots de passe", str(form.errors).lower())

    def test_church_user_create_form_rejects_weak_passwords(self):
        form = ChurchUserCreateForm(
            data={
                "username": "weak-password-user",
                "email": "weak-password-user@example.com",
                "role": ChurchMembership.Role.STAFF,
                "password1": "12345",
                "password2": "12345",
                "is_active": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password1", form.errors)

    def test_church_user_create_form_rolls_back_user_when_membership_creation_fails(self):
        church = self.create_church()
        form = ChurchUserCreateForm(
            data={
                "username": "rollback-user",
                "email": "rollback-user@example.com",
                "first_name": "Rollback",
                "last_name": "User",
                "phone": "+243810000200",
                "is_active": True,
                "role": ChurchMembership.Role.STAFF,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            }
        )

        self.assertTrue(form.is_valid())
        with patch("church.forms.ChurchMembership.objects.create", side_effect=RuntimeError("db error")):
            with self.assertRaises(RuntimeError):
                form.save(church=church)

        self.assertFalse(get_user_model().objects.filter(username="rollback-user").exists())

    def test_assign_form_rolls_back_when_membership_creation_fails(self):
        church = self.create_church()
        user = self.create_user(username="assign-rollback", email="assign-rollback@example.com")
        form = ChurchMembershipAssignForm(
            data={
                "identifier": user.username,
                "role": ChurchMembership.Role.SECRETARY,
            },
            church=church,
        )

        self.assertTrue(form.is_valid())
        with patch("church.forms.ChurchMembership.objects.create", side_effect=RuntimeError("db error")):
            with self.assertRaises(RuntimeError):
                form.save(church=church)

        self.assertFalse(ChurchMembership.objects.filter(user=user, church=church).exists())

    def test_invite_signup_form_rejects_existing_email(self):
        self.create_user(email="existing@example.com")
        form = InviteSignupForm(
            data={
                "username": "invite-new",
                "first_name": "Invite",
                "last_name": "User",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            email="existing@example.com",
        )

        self.assertFalse(form.is_valid())
        self.assertIn("connectez-vous", str(form.errors).lower())

    def test_church_invitation_form_rejects_duplicate_pending_invitation(self):
        church = self.create_church()
        invited_by = self.create_user(username="admin-email")
        ChurchInvitationForm(
            church=church,
            invited_by=invited_by,
        )
        self.create_invitation(church, "pending@example.com", invited_by=invited_by)

        form = ChurchInvitationForm(
            data={
                "email": "pending@example.com",
                "role": ChurchMembership.Role.STAFF,
            },
            church=church,
            invited_by=invited_by,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("invitation en attente", str(form.errors).lower())

