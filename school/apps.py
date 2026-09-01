from django.apps import AppConfig


class SchoolConfig(AppConfig):
    name = 'school'

    def ready(self):
        # Register the optional public-facing settings model.
        from . import public_models  # noqa: F401

        # Keep the existing URL name/path, while extending the school-info editor
        # without touching the large legacy views module.
        from . import views
        from .public_views import school_info_view
        views.school_info_view = school_info_view
