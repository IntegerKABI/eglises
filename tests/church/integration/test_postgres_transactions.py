"""PostgreSQL-specific transactional regression tests."""

from contextlib import closing
import unittest

import psycopg2
from psycopg2 import errors

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TransactionTestCase, override_settings

from church.models import Church, ChurchInvitation, ChurchMembership
from tests.factories import TEST_STORAGES


@override_settings(STORAGES=TEST_STORAGES)
class PostgreSQLTransactionTests(TransactionTestCase):
    """Exercise lock-sensitive membership flows on a real PostgreSQL connection."""

    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor != "postgresql":
            raise unittest.SkipTest(
                "PostgreSQL-specific transactional tests require a PostgreSQL database."
            )

    def setUp(self):
        self.user_model = get_user_model()
        self.invited_user = self.user_model.objects.create_user(
            username="invited-user",
            email="invited@example.com",
            password="StrongPass123!",
        )
        self.admin_user = self.user_model.objects.create_user(
            username="tenant-admin",
            email="admin@example.com",
            password="StrongPass123!",
        )
        self.church = Church.objects.create(name="Transactional Church")
        ChurchMembership.objects.create(
            user=self.admin_user,
            church=self.church,
            role=ChurchMembership.Role.ADMIN,
        )
        self.invitation = ChurchInvitation.objects.create(
            church=self.church,
            email=self.invited_user.email,
            role=ChurchMembership.Role.STAFF,
            invited_by=self.admin_user,
        )

    def test_invitation_row_lock_blocks_competing_for_update_queries(self):
        """Verify invitation acceptance locks behave as expected on PostgreSQL."""
        with transaction.atomic():
            locked_invitation = ChurchInvitation.objects.select_for_update().get(pk=self.invitation.pk)
            with closing(psycopg2.connect(**connection.get_connection_params())) as competing_connection:
                competing_connection.autocommit = False
                try:
                    with competing_connection.cursor() as cursor:
                        with self.assertRaises(errors.LockNotAvailable):
                            cursor.execute(
                                "SELECT id FROM church_churchinvitation WHERE id = %s FOR UPDATE NOWAIT",
                                [locked_invitation.pk],
                            )
                finally:
                    competing_connection.rollback()
