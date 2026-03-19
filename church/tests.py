from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ChurchInvitationForm, ChurchMembershipAssignForm
from .limits import (
    enforce_limits_for_model,
    filter_messages_for_retention,
    filter_notifications_for_retention,
)
from .models import (
    Church,
    ChurchInvitation,
    ChurchMembership,
    ContactMessage,
    Notification,
    Page,
    Sermon,
)
from .permissions import (
    CAP_MANAGE_EVENTS,
    CAP_SWITCH_CHURCH,
    CAP_VIEW_AUDIT,
    get_churches_for_capability,
    user_has_any_capability,
)


TEST_STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@override_settings(STORAGES=TEST_STORAGES)
class SingleChurchMembershipPolicyTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username="member",
            email="member@example.com",
            password="StrongPass123!",
        )
        self.church_one = Church.objects.create(name="Alpha Church")
        self.church_two = Church.objects.create(name="Beta Church")

    def test_non_superuser_cannot_have_two_active_memberships(self):
        ChurchMembership.objects.create(
            user=self.user,
            church=self.church_one,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            ChurchMembership.objects.create(
                user=self.user,
                church=self.church_two,
                role=ChurchMembership.Role.STAFF,
                is_active=True,
            )

    def test_invitation_form_rejects_existing_user_from_another_church(self):
        ChurchMembership.objects.create(
            user=self.user,
            church=self.church_one,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )

        form = ChurchInvitationForm(
            data={
                "email": self.user.email,
                "role": ChurchMembership.Role.STAFF,
            },
            church=self.church_two,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("une seule eglise active", str(form.errors).lower())

    def test_accept_invite_rejects_user_with_other_active_membership(self):
        ChurchMembership.objects.create(
            user=self.user,
            church=self.church_one,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )
        invite = ChurchInvitation.objects.create(
            church=self.church_two,
            email=self.user.email,
            role=ChurchMembership.Role.STAFF,
            invited_by=self.user,
        )

        self.client.force_login(self.user)
        response = self.client.post(reverse("accept_invite", args=[invite.token]))

        self.assertRedirects(
            response,
            reverse("pending_invitations"),
            fetch_redirect_response=False,
        )
        self.assertFalse(
            ChurchMembership.objects.filter(
                user=self.user,
                church=self.church_two,
                is_active=True,
            ).exists()
        )
        invite.refresh_from_db()
        self.assertEqual(invite.status, ChurchInvitation.Status.PENDING)


@override_settings(STORAGES=TEST_STORAGES)
class TenantLoginFlowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.password = "StrongPass123!"

    def test_single_church_user_redirects_to_dashboard(self):
        user = self.user_model.objects.create_user(
            username="single",
            email="single@example.com",
            password=self.password,
        )
        church = Church.objects.create(name="Single Church")
        ChurchMembership.objects.create(
            user=user,
            church=church,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.session.get("active_church_id"), church.id)

    def test_multi_church_non_superuser_is_redirected_home(self):
        user = self.user_model.objects.create_user(
            username="conflict",
            email="conflict@example.com",
            password=self.password,
        )
        church_one = Church.objects.create(name="Conflict One")
        church_two = Church.objects.create(name="Conflict Two")
        now = timezone.now()
        ChurchMembership.objects.bulk_create(
            [
                ChurchMembership(
                    user=user,
                    church=church_one,
                    role=ChurchMembership.Role.ADMIN,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                ChurchMembership(
                    user=user,
                    church=church_two,
                    role=ChurchMembership.Role.STAFF,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(
            response,
            reverse("home"),
            fetch_redirect_response=False,
        )
        self.assertIsNone(self.client.session.get("active_church_id"))

    def test_user_with_pending_invitation_is_redirected_to_invitation_inbox(self):
        user = self.user_model.objects.create_user(
            username="invitee",
            email="invitee@example.com",
            password=self.password,
        )
        church = Church.objects.create(name="Invite Church")
        ChurchInvitation.objects.create(
            church=church,
            email=user.email,
            role=ChurchMembership.Role.STAFF,
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(
            response,
            reverse("pending_invitations"),
            fetch_redirect_response=False,
        )

    def test_user_without_church_and_without_invitation_is_logged_out(self):
        user = self.user_model.objects.create_user(
            username="orphan",
            email="orphan@example.com",
            password=self.password,
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": self.password},
        )

        self.assertRedirects(
            response,
            reverse("home"),
            fetch_redirect_response=False,
        )
        self.assertIsNone(self.client.session.get("_auth_user_id"))


@override_settings(STORAGES=TEST_STORAGES)
class PendingInvitationWorkflowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username="pending",
            email="pending@example.com",
            password="StrongPass123!",
        )
        self.church = Church.objects.create(name="Pending Church")
        self.invite = ChurchInvitation.objects.create(
            church=self.church,
            email=self.user.email,
            role=ChurchMembership.Role.SECRETARY,
        )

    def test_pending_invitations_page_lists_matching_invites(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("pending_invitations"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.church.name)

    def test_decline_invite_marks_invitation_declined(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("decline_invite", args=[self.invite.token]))

        self.assertRedirects(
            response,
            reverse("home"),
            fetch_redirect_response=False,
        )
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, ChurchInvitation.Status.DECLINED)
        self.assertIsNotNone(self.invite.declined_at)
        self.assertIsNone(self.client.session.get("_auth_user_id"))


@override_settings(STORAGES=TEST_STORAGES)
class CapabilityConsistencyTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.admin_user = self.user_model.objects.create_user(
            username="audit-admin",
            email="audit-admin@example.com",
            password="StrongPass123!",
        )
        self.staff_user = self.user_model.objects.create_user(
            username="audit-staff",
            email="audit-staff@example.com",
            password="StrongPass123!",
        )
        self.superuser = self.user_model.objects.create_superuser(
            username="platform-root",
            email="root@example.com",
            password="StrongPass123!",
        )
        self.church_one = Church.objects.create(name="Audit Church")
        self.church_two = Church.objects.create(name="Second Audit Church")
        ChurchMembership.objects.create(
            user=self.admin_user,
            church=self.church_one,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )
        ChurchMembership.objects.create(
            user=self.staff_user,
            church=self.church_one,
            role=ChurchMembership.Role.STAFF,
            is_active=True,
        )

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
        self.client.force_login(self.staff_user)
        staff_response = self.client.get(reverse("manage_audit_logs"))
        self.assertRedirects(
            staff_response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )

        self.client.force_login(self.admin_user)
        self.client.session["active_church_id"] = self.church_one.id
        self.client.session.save()
        admin_response = self.client.get(reverse("manage_audit_logs"))
        self.assertEqual(admin_response.status_code, 200)


@override_settings(STORAGES=TEST_STORAGES)
class PlanLimitEnforcementTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_user(
            username="plan-admin",
            email="plan-admin@example.com",
            password="StrongPass123!",
        )
        self.extra_user = self.user_model.objects.create_user(
            username="plan-user",
            email="plan-user@example.com",
            password="StrongPass123!",
        )
        self.church = Church.objects.create(
            name="Plan Church",
            max_sermons_override=1,
            max_pages_override=1,
            max_users_override=1,
            max_pending_invitations_override=1,
            message_retention_days_override=30,
            notification_retention_days_override=15,
        )
        ChurchMembership.objects.create(
            user=self.admin,
            church=self.church,
            role=ChurchMembership.Role.ADMIN,
            is_active=True,
        )

    def test_sermon_limit_blocks_second_sermon(self):
        Sermon.objects.create(
            church=self.church,
            title="Premier sermon",
            created_by=self.admin,
        )

        with self.assertRaises(ValidationError):
            enforce_limits_for_model(self.church, Sermon)

    def test_page_limit_blocks_second_page(self):
        Page.objects.create(
            church=self.church,
            title="Premiere page",
            created_by=self.admin,
        )

        with self.assertRaises(ValidationError):
            enforce_limits_for_model(self.church, Page)

    def test_user_limit_blocks_membership_assignment(self):
        form = ChurchMembershipAssignForm(
            data={
                "identifier": self.extra_user.username,
                "role": ChurchMembership.Role.STAFF,
            },
            church=self.church,
        )
        self.assertTrue(form.is_valid(), form.errors)

        with self.assertRaises(ValidationError):
            form.save(self.church)

    def test_pending_invitation_limit_blocks_second_pending_invitation(self):
        ChurchInvitation.objects.create(
            church=self.church,
            email="first-invite@example.com",
            role=ChurchMembership.Role.STAFF,
            invited_by=self.admin,
        )
        form = ChurchInvitationForm(
            data={
                "email": "second-invite@example.com",
                "role": ChurchMembership.Role.SECRETARY,
            },
            church=self.church,
            invited_by=self.admin,
        )
        self.assertTrue(form.is_valid(), form.errors)

        with self.assertRaises(ValidationError):
            form.save()

    def test_retention_filters_old_notifications_and_resolved_messages(self):
        old_notification = Notification.objects.create(
            church=self.church,
            recipient=self.admin,
            category=Notification.Category.EVENT,
            title="Ancienne notification",
            is_read=False,
        )
        fresh_notification = Notification.objects.create(
            church=self.church,
            recipient=self.admin,
            category=Notification.Category.EVENT,
            title="Notification recente",
            is_read=False,
        )
        Notification.objects.filter(pk=old_notification.pk).update(
            created_at=timezone.now() - timedelta(days=20)
        )

        old_archived_message = ContactMessage.objects.create(
            church=self.church,
            sender_name="Ancien contact",
            sender_email="ancien@example.com",
            subject="Archive",
            message="Archive",
            status=ContactMessage.Status.ARCHIVED,
        )
        old_open_message = ContactMessage.objects.create(
            church=self.church,
            sender_name="Ancien ouvert",
            sender_email="ouvert@example.com",
            subject="Ouvert",
            message="Ouvert",
            status=ContactMessage.Status.NEW,
        )
        ContactMessage.objects.filter(pk=old_archived_message.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        ContactMessage.objects.filter(pk=old_open_message.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )

        retained_notifications = filter_notifications_for_retention(
            Notification.objects.filter(recipient=self.admin),
            [self.church],
        )
        retained_messages = filter_messages_for_retention(
            ContactMessage.objects.filter(church=self.church),
            self.church,
        )

        self.assertIn(fresh_notification, retained_notifications)
        self.assertNotIn(old_notification, retained_notifications)
        self.assertNotIn(old_archived_message, retained_messages)
        self.assertIn(old_open_message, retained_messages)
