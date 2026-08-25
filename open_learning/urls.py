from django.urls import path
from . import views, ai_views, plans_views

urlpatterns = [
    path('', views.lesson_list, name='open_learning_list'),
    path('lessons/add/', views.lesson_add, name='open_learning_add'),
    path('lessons/<int:lesson_id>/', views.lesson_detail, name='open_learning_lesson_detail'),
    path('lessons/<int:lesson_id>/edit/', views.lesson_edit, name='open_learning_lesson_edit'),
    path('lessons/<int:lesson_id>/delete/', views.lesson_delete, name='open_learning_lesson_delete'),
    path('lessons/<int:lesson_id>/submit/', views.lesson_submit, name='open_learning_lesson_submit'),
    path('lessons/<int:lesson_id>/approve/', views.lesson_approve, name='open_learning_lesson_approve'),
    path('lessons/<int:lesson_id>/publish/', views.lesson_publish, name='open_learning_lesson_publish'),
    path('lessons/<int:lesson_id>/reject/', views.lesson_reject, name='open_learning_lesson_reject'),
    path('lessons/<int:lesson_id>/archive/', views.lesson_archive, name='open_learning_lesson_archive'),
    path('lessons/<int:lesson_id>/resources/add/', views.resource_add, name='open_learning_resource_add'),
    path('lessons/<int:lesson_id>/resources/<int:resource_id>/delete/', views.resource_delete, name='open_learning_resource_delete'),
    path('lessons/<int:lesson_id>/resources/<int:resource_id>/open/', views.resource_open, name='ol_resource_open'),

    # ── طبقة الذكاء الاصطناعي (أفعال يدوية فقط، بدون استدعاء تلقائي) ──
    path('ai/generate/<int:lesson_id>/', ai_views.ai_generate_content, name='open_learning_ai_generate'),
    path('ai/section/<int:lesson_id>/', ai_views.ai_regenerate_section, name='open_learning_ai_section'),
    path('ai/search/<int:lesson_id>/', ai_views.ai_search_resources, name='open_learning_ai_search'),
    path('ai/update/<int:lesson_id>/', ai_views.ai_update_resources, name='open_learning_ai_update'),
    path('ai/approve-content/<int:lesson_id>/', ai_views.ai_approve_content, name='open_learning_ai_approve_content'),
    path('ai/approve-resource/<int:lesson_id>/<int:resource_id>/', ai_views.ai_approve_resource, name='open_learning_ai_approve_resource'),
    path('ai/reject-resource/<int:lesson_id>/<int:resource_id>/', ai_views.ai_reject_resource, name='open_learning_ai_reject_resource'),
    path('ai/dashboard/', ai_views.ai_dashboard, name='open_learning_ai_dashboard'),

    # ── تخزين Google Drive (للمدير فقط) ──
    path('storage-settings/', views.storage_settings, name='ol_storage_settings'),
    path('google-drive/connect/', views.google_drive_connect, name='ol_gdrive_connect'),
    path('google-drive/callback/', views.google_drive_callback, name='ol_gdrive_callback'),
    path('google-drive/disconnect/', views.google_drive_disconnect, name='ol_gdrive_disconnect'),

    # ── الخطة الأسبوعية ──
    path('plans/', plans_views.weekly_plan_list, name='ol_weekly_plan_list'),
    path('plans/add/', plans_views.weekly_plan_add, name='ol_weekly_plan_add'),
    path('plans/<int:plan_id>/', plans_views.weekly_plan_detail, name='ol_weekly_plan_detail'),
    path('plans/<int:plan_id>/review/', plans_views.weekly_plan_review, name='ol_weekly_plan_review'),
    path('plans/<int:plan_id>/delete/', plans_views.weekly_plan_delete, name='ol_weekly_plan_delete'),
]
