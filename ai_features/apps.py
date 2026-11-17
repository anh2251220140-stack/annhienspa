from django.apps import AppConfig

class AiFeaturesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_features"

    def ready(self):
        from .signals import connect
        connect()
