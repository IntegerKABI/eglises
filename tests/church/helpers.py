from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from church.models import Church, ChurchMembership


TEST_STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@override_settings(STORAGES=TEST_STORAGES)
class ChurchTestCase(TestCase):
    """Base de test avec fabriques simples pour les entités métier."""

    password = "StrongPass123!"

    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()
        self._user_sequence = 0
        self._church_sequence = 0

    def create_user(self, *, is_superuser=False, is_staff=False, **overrides):
        self._user_sequence += 1
        index = self._user_sequence
        defaults = {
            "username": f"user{index}",
            "email": f"user{index}@example.com",
            "password": self.password,
        }
        defaults.update(overrides)
        if is_superuser:
            return self.user_model.objects.create_superuser(**defaults)
        return self.user_model.objects.create_user(
            is_staff=is_staff,
            **defaults,
        )

    def create_church(self, **overrides):
        self._church_sequence += 1
        index = self._church_sequence
        defaults = {
            "name": f"Church {index}",
        }
        defaults.update(overrides)
        return Church.objects.create(**defaults)

    def add_membership(
        self,
        user,
        church,
        *,
        role=ChurchMembership.Role.ADMIN,
        is_active=True,
    ):
        return ChurchMembership.objects.create(
            user=user,
            church=church,
            role=role,
            is_active=is_active,
        )

    def login_to_church(self, user, church):
        self.client.force_login(user)
        session = self.client.session
        session["active_church_id"] = church.id
        session.save()
