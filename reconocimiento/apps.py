from django.apps import AppConfig


class ReconocimientoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reconocimiento'

    def ready(self):
        # Conecta las señales que invalidan la caché de encodings
        from . import signals  # noqa: F401
