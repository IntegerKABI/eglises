from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from church.models import (
    AuditLog,
    Church,
    ChurchInvitation,
    ChurchMembership,
    ContactMessage,
    Event,
    Member,
    Notification,
    Page,
    Sermon,
)


TEST_STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@override_settings(STORAGES=TEST_STORAGES)
class SaaSTestCase(TestCase):
    """Base de test avec fabriques l?g?res pour les objets m?tier."""

    password = "StrongPass123!"

    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()
        self._user_sequence = 0
        self._church_sequence = 0

    def create_user(self, *, is_superuser=False, is_staff=False, **overrides):
        self._user_sequence += 1
        defaults = {
            "username": f"user{self._user_sequence}",
            "email": f"user{self._user_sequence}@example.com",
            "password": self.password,
        }
        defaults.update(overrides)
        if is_superuser:
            return self.user_model.objects.create_superuser(**defaults)
        return self.user_model.objects.create_user(is_staff=is_staff, **defaults)

    def create_church(self, **overrides):
        self._church_sequence += 1
        defaults = {
            "name": f"Church {self._church_sequence}",
            "status": Church.Status.ACTIVE,
            "plan": Church.Plan.STARTER,
        }
        defaults.update(overrides)
        return Church.objects.create(**defaults)

    def add_membership(self, user, church, *, role=ChurchMembership.Role.ADMIN, is_active=True):
        return ChurchMembership.objects.create(
            user=user,
            church=church,
            role=role,
            is_active=is_active,
        )

    def create_event(self, church, **overrides):
        defaults = {
            "title": f"Event {timezone.now().timestamp()}",
            "event_date": date.today(),
            "is_active": True,
            "visibility": "public",
        }
        defaults.update(overrides)
        return Event.objects.create(church=church, **defaults)

    def create_sermon(self, church, **overrides):
        defaults = {
            "title": f"Sermon {timezone.now().timestamp()}",
            "is_active": True,
            "visibility": "public",
        }
        defaults.update(overrides)
        return Sermon.objects.create(church=church, **defaults)

    def create_member(self, church, **overrides):
        defaults = {
            "first_name": "Jean",
            "last_name": f"Member{timezone.now().timestamp()}",
            "is_active": True,
        }
        defaults.update(overrides)
        return Member.objects.create(church=church, **defaults)

    def create_page(self, church, **overrides):
        defaults = {
            "title": f"Page {timezone.now().timestamp()}",
            "content": "Contenu de test",
            "is_active": True,
            "visibility": "public",
            "is_in_menu": True,
        }
        defaults.update(overrides)
        return Page.objects.create(church=church, **defaults)

    def create_message(self, church, **overrides):
        defaults = {
            "sender_name": "Visiteur",
            "sender_email": "visiteur@example.com",
            "subject": "Sujet de test",
            "message": "Bonjour, ceci est un message de test.",
            "status": ContactMessage.Status.NEW,
        }
        defaults.update(overrides)
        return ContactMessage.objects.create(church=church, **defaults)

    def create_notification(self, church, recipient, **overrides):
        defaults = {
            "category": Notification.Category.EVENT,
            "title": "Notification de test",
            "body": "Contenu de test",
            "is_read": False,
        }
        defaults.update(overrides)
        return Notification.objects.create(church=church, recipient=recipient, **defaults)

    def create_invitation(self, church, email, **overrides):
        defaults = {
            "role": ChurchMembership.Role.STAFF,
        }
        defaults.update(overrides)
        return ChurchInvitation.objects.create(church=church, email=email, **defaults)

    def create_audit_log(self, church=None, actor=None, **overrides):
        defaults = {
            "action": "create",
            "object_type": "TestObject",
            "object_id": "1",
            "object_repr": "Objet de test",
            "metadata": {},
        }
        defaults.update(overrides)
        return AuditLog.objects.create(church=church, actor=actor, **defaults)

    def login_to_church(self, user, church):
        self.client.force_login(user)
        session = self.client.session
        session["active_church_id"] = church.id
        session.save()

