from django.core.exceptions import ValidationError

from church.forms import (
    ChurchInvitationForm,
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

