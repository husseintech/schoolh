from django.urls import path

from .supervisor_followup_views import supervisor_visit_followup

urlpatterns = [
    path('supervisor-visits/<int:visit_id>/followup/', supervisor_visit_followup, name='supervisor_visit_followup'),
]
