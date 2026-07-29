from .models import has_perm


def user_permissions(request):
    """Add user permissions to template context for sidebar display."""
    perms = set()
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
        ]
        for module, action in modules_actions:
            if has_perm(request.user, module, action):
                perms.add(f'{module}_{action}')
    return {'user_perms': perms}
