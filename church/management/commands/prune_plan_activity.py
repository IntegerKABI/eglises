"""Purge activity records that exceed plan retention windows."""

from django.core.management.base import BaseCommand

from church.limits import purge_expired_activity
from church.models import Church


class Command(BaseCommand):
    help = (
        'Delete expired notifications and archived/responded messages '
        'outside each church plan retention window.'
    )

    def handle(self, *args, **options):
        total_notifications = 0
        total_messages = 0

        for church in Church.objects.all().only('id', 'name'):
            summary = purge_expired_activity(church)
            total_notifications += summary['notifications_deleted']
            total_messages += summary['messages_deleted']
            self.stdout.write(
                f"{church.name}: "
                f"{summary['notifications_deleted']} notifications, "
                f"{summary['messages_deleted']} messages supprimes"
            )

        self.stdout.write(
            self.style.SUCCESS(
                'Nettoyage termine - '
                f'{total_notifications} notifications, '
                f'{total_messages} messages supprimes'
            )
        )
