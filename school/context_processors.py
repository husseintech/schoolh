from django.conf import settings
from django.urls import reverse
from .models import has_perm, Notification, Message, SchoolInfo
from .services import send_visit_reminders
from .student_assistant import assistant_settings, quick_prompts, student_short_name
from .student_guide import build_student_guide_tasks


def user_permissions(request):
    """Add user permissions, notification and message counts to template context."""
    perms = set()
    unread_count = 0
    recent_notifications = []
    unread_messages_count = 0
    recent_messages = []
    account_display_name = ''
    show_attendance_register = False
    show_grade_register = False
    student_guide_tasks = []
    student_assistant_config = {'enabled': False}
    school_info = SchoolInfo.objects.first()
    if request.user.is_authenticated:
        user = request.user
        role = getattr(getattr(user, 'profile', None), 'role', None)
        relation = {'teacher': 'teacher_profile', 'student': 'student_profile'}.get(role)
        person = getattr(user, relation, None) if relation else None
        account_display_name = (
            (getattr(person, 'full_name', '') or '').strip()
            or user.get_full_name().strip()
            or user.username
        )
        show_attendance_register = role == 'admin' or bool(
            role == 'teacher' and person and getattr(person, 'guardian_class', None)
        )
        show_grade_register = role in ('admin', 'teacher')
        send_visit_reminders()
        modules_actions = [
            ('students', 'view'), ('students', 'add'), ('students', 'edit'),
            ('students', 'delete'), ('students', 'import'), ('students', 'export'),
            ('teachers', 'view'), ('teachers', 'add'), ('teachers', 'edit'),
            ('teachers', 'delete'), ('teachers', 'notes'),
            ('classes', 'view'), ('classes', 'add'), ('classes', 'delete'),
            ('subjects', 'view'), ('subjects', 'add'), ('subjects', 'delete'),
            ('announcements', 'view'), ('announcements', 'add'), ('announcements', 'delete'),
            ('agenda', 'view'), ('agenda', 'add'), ('agenda', 'complete'), ('agenda', 'delete'),
            ('leaves', 'view'), ('leaves', 'add'), ('leaves', 'delete'),
            ('levels', 'view'), ('levels', 'add'),
            ('exams', 'view'), ('exams', 'add'),
            ('messages', 'view'), ('messages', 'send'),
            ('reports', 'view'),
            ('settings', 'whatsapp'), ('settings', 'accounts'),
            ('settings', 'links'),
            ('notes', 'view'), ('notes', 'add'),
            ('discipline', 'view'), ('discipline', 'add'),
            ('lateness', 'view'), ('lateness', 'add'),
            ('meetings', 'view'), ('meetings', 'add'),
            ('supervisor_visits', 'view'), ('supervisor_visits', 'add'),
            ('inspection_visits', 'view'), ('inspection_visits', 'add'),
            ('visit_program', 'view'), ('visit_program', 'add'), ('visit_program', 'delete'),
            ('absence', 'view'), ('absence', 'add'),
            ('schedule', 'view'), ('schedule', 'add'), ('schedule', 'edit'), ('schedule', 'delete'), ('schedule', 'generate'), ('schedule', 'export'), ('schedule', 'print'), ('schedule', 'manage_constraints'), ('schedule', 'manage_settings'),
            ('survey', 'view'), ('survey', 'add'),
            ('certificates', 'view'), ('certificates', 'add'), ('certificates', 'delete'),
            ('guardians', 'view'), ('guardians', 'add'),
            ('nominations', 'view'), ('nominations', 'add'),
            ('incoming', 'view'), ('incoming', 'add'), ('incoming', 'delete'),
            ('outgoing', 'view'), ('outgoing', 'add'), ('outgoing', 'delete'),
            ('teacher_followup', 'view'), ('teacher_followup', 'add'), ('teacher_followup', 'delete'),
            ('reciprocal_visits', 'view'), ('reciprocal_visits', 'add'), ('reciprocal_visits', 'delete'),
            ('no_objection', 'view'), ('no_objection', 'add'), ('no_objection', 'delete'),
            ('open_learning', 'view'), ('open_learning', 'add'), ('open_learning', 'review'),
            ('school_radio', 'view'), ('school_radio', 'add'), ('school_radio', 'edit'),
            ('school_radio', 'delete'), ('school_radio', 'generate'), ('school_radio', 'review'),
        ]
        for module, action in modules_actions:
            if has_perm(request.user, module, action):
                perms.add(f'{module}_{action}')
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        recent_notifications = Notification.objects.filter(user=request.user).exclude(link__startswith='/messages/')[:5]
        unread_messages_count = Message.objects.filter(recipient=request.user, is_read=False).count()
        recent_messages = Message.objects.filter(recipient=request.user)[:5]
        if role == 'student' and person:
            assistant_config_obj = assistant_settings()
            if assistant_config_obj.enabled:
                student_unread_notifications = Notification.objects.filter(
                    user=request.user,
                    is_read=False,
                ).exclude(link__startswith='/messages/').count()
                has_survey = hasattr(person, 'survey')
                student_guide_tasks = build_student_guide_tasks(
                    student=person,
                    can_add_survey=has_perm(request.user, 'survey', 'add'),
                    has_survey=has_survey,
                    unread_notifications=student_unread_notifications,
                    unread_messages=unread_messages_count,
                    warnings_count=person.warnings.count(),
                    summons_count=person.summons.count(),
                )
                current_url_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '')
                student_assistant_config = {
                    'enabled': True,
                    'welcome_pending': bool(request.session.pop('student_assistant_welcome_pending', False)),
                    'auto_open': current_url_name == 'dashboard',
                    'short_name': student_short_name(person.full_name),
                    'school_name': school_info.name_ar if school_info else 'مدرستك',
                    'welcome_message': assistant_config_obj.welcome_message,
                    'ask_url': reverse('student_assistant_ask'),
                    'daily_ai_limit': assistant_config_obj.daily_ai_limit,
                    'educational_ai_enabled': assistant_config_obj.educational_ai_enabled,
                    'quick_prompts': quick_prompts(person),
                }
    return {
        'account_display_name': account_display_name,
        'show_attendance_register': show_attendance_register,
        'show_grade_register': show_grade_register,
        'user_perms': perms,
        'school_info': school_info,
        'unread_notifications_count': unread_count,
        'recent_notifications': recent_notifications,
        'unread_messages_count': unread_messages_count,
        'recent_messages': recent_messages,
        'vapid_public_key': settings.VAPID_PUBLIC_KEY,
        'word_export': request.GET.get('export') == 'word',
        'student_guide_tasks': student_guide_tasks,
        'student_assistant_config': student_assistant_config,
    }
