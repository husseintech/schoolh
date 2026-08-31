from django.apps import AppConfig


class OpenLearningConfig(AppConfig):
    name = 'open_learning'

    def ready(self):
        # Register extension models only; no database queries are performed here.
        from . import progress_models  # noqa: F401
        from . import learning_models  # noqa: F401

        # Install a production-safe AI provider selector. It prefers Gemini when
        # configured, but falls back to the built-in local generator at no cost.
        from .services.provider_runtime import install_provider_override
        install_provider_override()
