from django.apps import AppConfig


class SubmissionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'submissions'

    def ready(self):
        import submissions.signals  # noqa: F401 — registers post_save signal
