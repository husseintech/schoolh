from django.apps import AppConfig


class OpenLearningConfig(AppConfig):
    name = 'open_learning'

    def ready(self):
        # Register extension models only; no database queries are performed here.
        from . import progress_models  # noqa: F401
        from . import learning_models  # noqa: F401
        from . import enhancement_models  # noqa: F401

        # Select a real provider; unavailable AI must never return template text.
        from .services.provider_runtime import install_provider_override
        install_provider_override()
