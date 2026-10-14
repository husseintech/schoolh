from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0064_student_display_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeacherFollowupRegisterSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('criteria', models.JSONField(blank=True, default=list, verbose_name='بنود المتابعة وأوزانها')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('teacher', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='followup_register_settings', to='school.teacher', verbose_name='المعلم')),
            ],
            options={
                'verbose_name': 'إعدادات دفتر متابعة المعلم',
                'verbose_name_plural': 'إعدادات دفاتر متابعة المعلمين',
            },
        ),
    ]
}
