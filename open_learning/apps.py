from django.apps import AppConfig


class OpenLearningConfig(AppConfig):
    name = 'open_learning'

    def ready(self):
        # Models kept in a separate module to avoid disturbing the existing
        # open-learning models file while this feature is being developed.
        from . import progress_models  # noqa: F401
