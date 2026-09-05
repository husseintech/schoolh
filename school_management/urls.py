"""URL configuration for school_management project."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from school.academic_report_views import academic_achievement_report
from school.health_views import database_health
from school.note_actions import delete_note

urlpatterns = [
    path('health/database/', database_health, name='database_health'),
    path('admin/', admin.site.urls),
    path('administration/academic-achievement/', academic_achievement_report, name='academic_achievement_report'),
    path('administration/teacher-records/', include('school.teacher_records_urls')),
    path('notes/<int:note_id>/delete/', delete_note, name='delete_note'),
    path('', include('school.supervisor_followup_urls')),
    path('', include('school.urls')),
    path('open-learning/', include('open_learning.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
