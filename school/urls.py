from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Students
    path('students/', views.student_list, name='student_list'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/<int:student_id>/edit/', views.edit_student, name='edit_student'),
    path('students/<int:student_id>/delete/', views.delete_student, name='delete_student'),
    path('students/<int:student_id>/notes/', views.student_notes, name='student_notes'),
    path('students/<int:student_id>/detail/', views.student_detail, name='student_detail'),

    # Excel Import/Export
    path('students/download-template/', views.download_student_template, name='download_student_template'),
    path('students/import/', views.import_students, name='import_students'),
    path('students/export/', views.export_students, name='export_students'),

    # Notes
    path('notes/add/', views.add_note, name='add_note'),
    path('notes/', views.note_list, name='note_list'),

    # Teachers
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/add/', views.add_teacher, name='add_teacher'),
    path('teachers/<int:teacher_id>/edit/', views.edit_teacher, name='edit_teacher'),
    path('teachers/<int:teacher_id>/delete/', views.delete_teacher, name='delete_teacher'),
    path('teachers/<int:teacher_id>/notes/', views.teacher_notes, name='teacher_notes'),
    path('teachers/<int:teacher_id>/notes/add/', views.add_teacher_note, name='add_teacher_note'),

    # Classes
    path('classes/', views.class_list, name='class_list'),
    path('classes/add/', views.add_class, name='add_class'),
    path('classes/<int:class_id>/delete/', views.delete_class, name='delete_class'),

    # Subjects
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/add/', views.add_subject, name='add_subject'),
    path('subjects/<int:subject_id>/delete/', views.delete_subject, name='delete_subject'),

    # Announcements
    path('announcements/', views.announcement_list, name='announcement_list'),
    path('announcements/add/', views.add_announcement, name='add_announcement'),
    path('announcements/<int:announcement_id>/delete/', views.delete_announcement, name='delete_announcement'),

    # Agenda
    path('agenda/', views.agenda_list, name='agenda_list'),
    path('agenda/add/', views.add_agenda, name='add_agenda'),
    path('agenda/<int:agenda_id>/complete/', views.complete_agenda, name='complete_agenda'),
    path('agenda/<int:agenda_id>/uncomplete/', views.uncomplete_agenda, name='uncomplete_agenda'),
    path('agenda/<int:agenda_id>/delete/', views.delete_agenda, name='delete_agenda'),

    # Student Leave
    path('leaves/', views.leave_list, name='leave_list'),
    path('leaves/add/', views.add_leave, name='add_leave'),
    path('leaves/<int:leave_id>/delete/', views.delete_leave, name='delete_leave'),

    # Student Levels
    path('levels/', views.student_level_list, name='student_level_list'),
    path('levels/add/', views.add_student_level, name='add_student_level'),

    # Exam Analysis
    path('exam-analysis/', views.exam_analysis_list, name='exam_analysis_list'),
    path('exam-analysis/add/', views.add_exam_analysis, name='add_exam_analysis'),

    # Messages
    path('contact/', views.parent_message, name='parent_message'),
    path('messages/', views.message_list, name='message_list'),
    path('messages/send/', views.send_message, name='send_message'),
    path('messages/sent/', views.sent_messages, name='sent_messages'),
    path('messages/<int:message_id>/read/', views.read_message, name='read_message'),
    path('messages/student/', views.student_messages, name='student_messages'),

    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/overview/', views.reports_overview, name='reports_overview'),
    path('reports/class/<int:class_id>/', views.class_report, name='class_report'),

    # WhatsApp
    path('whatsapp-settings/', views.whatsapp_settings, name='whatsapp_settings'),
]
