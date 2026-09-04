from django.db import migrations


SENSITIVE_VISIT_MODULES = ('supervisor_visits', 'inspection_visits')


def remove_legacy_teacher_visit_permissions(apps, schema_editor):
    UserPermission = apps.get_model('school', 'UserPermission')
    permissions_rows = UserPermission.objects.filter(user__profile__role='teacher')

    for permissions_row in permissions_rows.iterator():
        permissions = dict(permissions_row.permissions or {})
        changed = False
        for module in SENSITIVE_VISIT_MODULES:
            if module in permissions:
                permissions.pop(module)
                changed = True
        if changed:
            permissions_row.permissions = permissions
            permissions_row.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0048_login_event_history'),
    ]

    operations = [
        migrations.RunPython(
            remove_legacy_teacher_visit_permissions,
            migrations.RunPython.noop,
        ),
    ]
