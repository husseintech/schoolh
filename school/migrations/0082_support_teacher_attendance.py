from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0081_support_subject_and_followup_dates'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportTeacherAttendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attendance_date', models.DateField(verbose_name='التاريخ')),
                ('check_in_time', models.TimeField(default='07:30', verbose_name='بداية الدوام')),
                ('check_out_time', models.TimeField(default='14:30', verbose_name='نهاية الدوام')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='وقت التسجيل')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='support_attendance', to='school.teacher', verbose_name='المعلم المساند')),
            ],
            options={
                'verbose_name': 'بصمة دوام معلم مساند',
                'verbose_name_plural': 'بصمات دوام المعلمين المساندين',
                'ordering': ['-attendance_date'],
            },
        ),
        migrations.AddConstraint(
            model_name='supportteacherattendance',
            constraint=models.UniqueConstraint(fields=('teacher', 'attendance_date'), name='unique_support_attendance_day'),
        ),
    ]
