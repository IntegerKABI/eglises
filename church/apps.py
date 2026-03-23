from django.apps import AppConfig


class ChurchConfig(AppConfig):
    name = 'church'

    def ready(self):
        import church.signals  # noqa
