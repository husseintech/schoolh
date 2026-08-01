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
    path('students/<int:student_id>/report/', views.student_report, name='student_report'),
    path('students/<int:student_id>/reset-password/', views.reset_student_password, name='reset_student_password'),

    # Excel Import/Export
    path('students/download-template/', views.download_student_template, name='download_student_template'),
    path('students/import/', views.import_students, name='import_students'),
    path('students/export/', views.export_students, name='export_students'),

    # Notes
    path('notes/add/', views.add_note, name='add_note'),
    path('notes/add/<int:student_id>/', views.add_note, name='add_note_with_student'),
    path('notes/', views.note_list, name='note_list'),

    # Teachers
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/add/', views.add_teacher, name='add_teacher'),
    path('teachers/<int:teacher_id>/edit/', views.edit_teacher, name='edit_teacher'),
    path('teachers/<int:teacher_id>/delete/', views.delete_teacher, name='delete_teacher'),
    path('teachers/<int:teacher_id>/notes/', views.teacher_notes, name='teacher_notes'),
    path('teachers/<int:teacher_id>/notes/add/', views.add_teacher_note, name='add_teacher_note'),
    path('teachers/report/', views.teachers_report, name='teachers_report'),
    path('teachers/cards/', views.teacher_cards_report, name='teacher_cards_report'),
    path('notes/report/', views.notes_report, name='notes_report'),

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
    path('leaves/add/<int:student_id>/', views.add_leave, name='add_leave_with_student'),
    path('leaves/<int:leave_id>/delete/', views.delete_leave, name='delete_leave'),

    # Student Levels
    path('levels/', views.student_level_list, name='student_level_list'),
    path('levels/add/', views.add_student_level, name='add_student_level'),
    path('levels/bulk-add/', views.bulk_add_student_level, name='bulk_add_student_level'),

    # Exam Analysis
    path('exam-analysis/', views.exam_analysis_list, name='exam_analysis_list'),
    path('exam-analysis/add/', views.add_exam_analysis, name='add_exam_analysis'),

    # Messages
    path('contact/', views.parent_message, name='parent_message'),
    path('messages/', views.message_list, name='message_list'),
    path('messages/send/', views.send_message, name='send_message'),
    path('messages/send/<int:user_id>/', views.send_message, name='send_message_to'),
    path('messages/report/', views.messages_report, name='messages_report'),
    path('messages/sent/', views.sent_messages, name='sent_messages'),
    path('messages/<int:message_id>/read/', views.read_message, name='read_message'),
    path('messages/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('messages/delete-all-sent/', views.delete_all_sent_messages, name='delete_all_sent_messages'),
    path('messages/delete-all-received/', views.delete_all_received_messages, name='delete_all_received_messages'),
    path('messages/delete-all/', views.delete_all_messages, name='delete_all_messages'),
    path('messages/student/', views.student_messages, name='student_messages'),

    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/overview/', views.reports_overview, name='reports_overview'),
    path('reports/class/<int:class_id>/', views.class_report, name='class_report'),
    path('reports/student-levels/', views.student_levels_report, name='student_levels_report'),

    # Account Management
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/add/', views.add_account, name='add_account'),
    path('accounts/<int:user_id>/edit/', views.edit_account, name='edit_account'),
    path('accounts/<int:user_id>/delete/', views.delete_account, name='delete_account'),

    # My Account
    path('my-account/', views.my_account, name='my_account'),

    # WhatsApp
    path('whatsapp-settings/', views.whatsapp_settings, name='whatsapp_settings'),

    # Lesson Links
    path('lesson-links/', views.lesson_link_list, name='lesson_link_list'),
    path('lesson-links/add/', views.add_lesson_link, name='add_lesson_link'),
    path('lesson-links/<int:link_id>/delete/', views.delete_lesson_link, name='delete_lesson_link'),

    # Student Lateness
    path('lateness/', views.lateness_list, name='lateness_list'),
    path('lateness/report/', views.lateness_report, name='lateness_report'),
    path('lateness/student/<int:student_id>/', views.student_lateness_detail, name='student_lateness_detail'),

    # School Info
    path('school-info/', views.school_info_view, name='school_info'),

    # Meetings
    path('meetings/', views.meeting_list, name='meeting_list'),
    path('meetings/add/', views.add_meeting, name='add_meeting'),
    path('meetings/<int:meeting_id>/report/', views.meeting_report, name='meeting_report'),

    # Supervisor Visits
    path('supervisor-visits/', views.supervisor_visit_list, name='supervisor_visit_list'),
    path('supervisor-visits/<int:visit_id>/report/', views.supervisor_visit_report, name='supervisor_visit_report'),
    path('supervisor-visits/all-report/', views.supervisor_visits_report, name='supervisor_visits_report'),

    # Inspection Visits (Principal)
    path('inspection-visits/', views.inspection_visit_list, name='inspection_visit_list'),
    path('inspection-visits/<int:visit_id>/report/', views.inspection_visit_report, name='inspection_visit_report'),
    path('inspection-visits/all-report/', views.inspection_visits_all_report, name='inspection_visits_all_report'),

    # Visit Program
    path('visit-program/', views.visit_program_list, name='visit_program_list'),
    path('visit-program/<int:entry_id>/delete/', views.visit_program_delete, name='visit_program_delete'),
    path('visit-program/<int:entry_id>/update/', views.visit_program_update, name='visit_program_update'),
    path('visit-program/report/', views.visit_program_report, name='visit_program_report'),
    path('visit-program/report/missing-notes/', views.visit_program_missing_notes_report, name='visit_program_missing_notes_report'),

    # Notifications
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/<int:notification_id>/read/', views.notification_read, name='notification_read'),

    # Daily schedule
    path('schedule/', views.schedule_grid, name='schedule_grid'),
    path('schedule/print-day/', views.schedule_print_day, name='schedule_print_day'),
    path('schedule/print-teacher/', views.schedule_print_teacher, name='schedule_print_teacher'),

    # Absence
    path('absence/', views.absence_list, name='absence_list'),
    path('absence/report/', views.absence_report, name='absence_report'),

    # PWA
    path('sw.js', views.service_worker, name='service_worker'),
    path('manifest.json', views.manifest_view, name='manifest'),
    path('push/subscribe/', views.push_subscribe, name='push_subscribe'),
    path('push/unsubscribe/', views.push_unsubscribe, name='push_unsubscribe'),
    path('push/test/', views.push_test, name='push_test'),

    # Guardians
    path('guardians/', views.guardian_assign, name='guardian_assign'),
    path('guardians/students/', views.guardian_students, name='guardian_students'),

    # Certificates (outstanding students)
    path('certificates/manage/', views.certificates_manage, name='certificates_manage'),
    path('certificates/<int:nomination_id>/print/', views.certificate_print, name='certificate_print'),
    path('certificates/print-all/', views.certificates_print_all, name='certificates_print_all'),
    path('certificates/export/', views.certificates_export, name='certificates_export'),
]
