from django.apps import AppConfig


class SchoolConfig(AppConfig):
    name = 'school'

    def ready(self):
        # Register the optional public-facing settings model.
        from . import public_models  # noqa: F401

        # Keep existing URL names while extending selected legacy views safely.
        from . import views
        from .public_views import school_info_view
        from .academic_report_views import academic_achievement_report
        views.school_info_view = school_info_view
        views.academic_achievement_report = academic_achievement_report
