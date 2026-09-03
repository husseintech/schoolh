from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def seed_last_known_login(apps, schema_editor):
    Profile = apps.get_model('school', 'Profile')
    LoginEvent = apps.get_model('school', 'LoginEvent')
    historical_events = []

    profiles = Profile.objects.filter(
        role__in=['teacher', 'student'],
        user__last_login__isnull=False,
    ).select_related('user')
    for profile in profiles.iterator():
        historical_events.append(LoginEvent(
            user_id=profile.user_id,
            role=profile.role,
            logged_at=profile.user.last_login,
        ))

    LoginEvent.objects.bulk_create(historical_events, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0047_studentsurvey_digital_health'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('teacher', 'معلم'), ('student', 'طالب')], max_length=20, verbose_name='نوع الحساب')),
                ('logged_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='وقت الدخول')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_events', to='auth.user', verbose_name='الحساب')),
            ],
            options={
                'verbose_name': 'عملية دخول',
                'verbose_name_plural': 'سجل عمليات الدخول',
                'ordering': ['-logged_at'],
                'indexes': [
                    models.Index(fields=['user', '-logged_at'], name='login_user_time_idx'),
                    models.Index(fields=['role', '-logged_at'], name='login_role_time_idx'),
                ],
            },
        ),
        migrations.RunPython(seed_last_known_login, migrations.RunPython.noop),
    ]
