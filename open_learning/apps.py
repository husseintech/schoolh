from django.apps import AppConfig


class OpenLearningConfig(AppConfig):
    name = 'open_learning'

    def ready(self):
        # Register extension models only; no database queries are performed here.
        from . import progress_models  # noqa: F401
        from . import learning_models  # noqa: F401
