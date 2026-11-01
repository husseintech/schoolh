from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0081_support_subject_and_followup_dates'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TeacherMonthlyAttendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attendance_date', models.DateField(db_index=True, verbose_name='تاريخ الدوام')),
                ('check_in_at', models.DateTimeField(blank=True, null=True, verbose_name='وقت بداية الدوام')),
                ('check_out_at', models.DateTimeField(blank=True, null=True, verbose_name='وقت نهاية الدوام')),
                ('notes', models.CharField(blank=True, max_length=500, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='وقت الإدخال الفعلي')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('last_recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_original_teacher_attendance', to=settings.AUTH_USER_MODEL, verbose_name='سجل بواسطة')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='monthly_attendance_records', to='school.teacher', verbose_name='المعلم الأصيل')),
            ],
            options={'verbose_name': 'بصمة دوام معلم أصيل', 'verbose_name_plural': 'بصمة دوام المعلمين الأصيلين', 'ordering': ['attendance_date', 'id']},
        ),
        migrations.AddConstraint(
            model_name='teachermonthlyattendance',
            constraint=models.UniqueConstraint(fields=('teacher', 'attendance_date'), name='unique_original_teacher_attendance_day'),
        ),
    ]
