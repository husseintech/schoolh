"""URL configuration for school_management project."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from school.academic_report_views import academic_achievement_report
from school.health_views import database_health
from school.note_actions import delete_note
from school.health_views import database_heartbeat
from school.ad_studio_views import school_ad_studio
from school.ai_ad_views import generate_ad_background
from school.facebook_ad_views import (
    facebook_connect, facebook_callback, facebook_select_page, facebook_disconnect, facebook_publish_announcement,
)

urlpatterns = [
    path('health/database/', database_health, name='database_health'),
    path('health/database-heartbeat/', database_heartbeat, name='database_heartbeat'),
    path('admin/', admin.site.urls),
    path('administration/academic-achievement/', academic_achievement_report, name='academic_achievement_report'),
    path('administration/teacher-records/', include('school.teacher_records_urls')),
    path('administration/ad-studio/', school_ad_studio, name='school_ad_studio'),
    path('administration/ad-studio/generate-background/', generate_ad_background, name='generate_ad_background'),
    path('facebook/connect/', facebook_connect, name='facebook_connect'),
    path('facebook/callback/', facebook_callback, name='facebook_callback'),
    path('facebook/select-page/', facebook_select_page, name='facebook_select_page'),
    path('facebook/disconnect/', facebook_disconnect, name='facebook_disconnect'),
    path('facebook/publish-announcement/', facebook_publish_announcement, name='facebook_publish_announcement'),
    path('notes/<int:note_id>/delete/', delete_note, name='delete_note'),
    path('', include('school.supervisor_followup_urls')),
    path('', include('school.urls')),
    path('open-learning/', include('open_learning.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
