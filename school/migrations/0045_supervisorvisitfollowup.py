from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0044_classsubjectmapping'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SupervisorVisitFollowup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('followup_date', models.DateField(verbose_name='تاريخ متابعة الإدارة')),
                ('notes', models.TextField(verbose_name='متابعة الإدارة')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supervisor_visit_followups', to=settings.AUTH_USER_MODEL, verbose_name='سجل بواسطة')),
                ('visit', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='management_followup', to='school.supervisorvisit', verbose_name='زيارة المشرف')),
            ],
            options={
                'verbose_name': 'متابعة زيارة مشرف',
                'verbose_name_plural': 'متابعات زيارات المشرفين',
                'ordering': ['-followup_date', '-updated_at'],
            },
        ),
    ]
