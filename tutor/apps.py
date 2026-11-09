from django.apps import AppConfig


class TutorConfig(AppConfig):
    name = 'tutor'

    def ready(self):
        from . import signals  # noqa: F401
