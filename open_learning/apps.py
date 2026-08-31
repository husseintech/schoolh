from django.apps import AppConfig


class OpenLearningConfig(AppConfig):
    name = 'open_learning'

    def ready(self):
        # Extension models are isolated while the new learning suite is developed.
        from . import progress_models  # noqa: F401
        from . import learning_models  # noqa: F401
