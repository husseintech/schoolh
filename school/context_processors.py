from .models import has_perm, Notification, Message


def user_permissions(request):
    """Add user permissions, notification and message counts to template context."""
    perms = set()
    unread_count = 0
    recent_notifications = []
    unread_messages_count = 0
    recent_messages = []
    if request.user.is_authenticated:
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
            ('lateness', 'view'), ('lateness', 'add'),
            ('meetings', 'view'), ('meetings', 'add'),
            ('supervisor_visits', 'view'), ('supervisor_visits', 'add'),
            ('inspection_visits', 'view'), ('inspection_visits', 'add'),
        ]
        for module, action in modules_actions:
            if has_perm(request.user, module, action):
                perms.add(f'{module}_{action}')
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        recent_notifications = Notification.objects.filter(user=request.user).exclude(link__startswith='/messages/')[:5]
        unread_messages_count = Message.objects.filter(recipient=request.user, is_read=False).count()
        recent_messages = Message.objects.filter(recipient=request.user)[:5]
    return {
        'user_perms': perms,
        'unread_notifications_count': unread_count,
        'recent_notifications': recent_notifications,
        'unread_messages_count': unread_messages_count,
        'recent_messages': recent_messages,
    }
