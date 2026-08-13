from django.urls import path
from . import views

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
]
