from django.apps import AppConfig


class DatasyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "datasync"

    def ready(self):
        import datasync.signals  # noqa: F401
