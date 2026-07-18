from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/', views.student_list, name='student_list'),
    path('students/<int:student_id>/edit/', views.edit_student, name='edit_student'),
    path('students/<int:student_id>/delete/', views.delete_student, name='delete_student'),
    path('students/<int:student_id>/notes/', views.student_notes, name='student_notes'),
    path('notes/add/', views.add_note, name='add_note'),
    path('notes/', views.note_list, name='note_list'),
    path('whatsapp-settings/', views.whatsapp_settings, name='whatsapp_settings'),
]
