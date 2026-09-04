from django.db import migrations


def enable_student_admin_messages(apps, schema_editor):
    UserPermission = apps.get_model('school', 'UserPermission')
    rows = UserPermission.objects.filter(user__profile__role='student')
    for row in rows.iterator():
        permissions = dict(row.permissions or {})
        actions = list(permissions.get('messages', []))
        if 'send' not in actions:
            actions.append('send')
            permissions['messages'] = actions
            row.permissions = permissions
            row.save(update_fields=['permissions'])


def disable_student_admin_messages(apps, schema_editor):
    UserPermission = apps.get_model('school', 'UserPermission')
    rows = UserPermission.objects.filter(user__profile__role='student')
    for row in rows.iterator():
        permissions = dict(row.permissions or {})
        actions = [action for action in permissions.get('messages', []) if action != 'send']
        permissions['messages'] = actions
        row.permissions = permissions
        row.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0049_reset_teacher_visit_permissions'),
    ]

    operations = [
        migrations.RunPython(enable_student_admin_messages, disable_student_admin_messages),
    ]
