from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"

    def ready(self):
        """Importar signals e modulos adicionais quando o app estiver pronto"""
        import dashboard.models.audit  # noqa: F401
        import dashboard.signals  # noqa: F401
        import dashboard.utils.rbac  # noqa: F401
