from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('open_learning', '0009_remove_learninglesson_student_class_and_more'),
        ('school', '0040_noobjection_extra_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentLessonProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('not_started', 'لم يبدأ'), ('in_progress', 'قيد التعلم'), ('completed', 'مكتمل')], default='not_started', max_length=20, verbose_name='الحالة')),
                ('first_started_at', models.DateTimeField(blank=True, null=True, verbose_name='أول بدء')),
                ('last_activity_at', models.DateTimeField(blank=True, null=True, verbose_name='آخر نشاط')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='تاريخ الإكمال')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_progress', to='open_learning.learninglesson', verbose_name='الدرس')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='open_learning_progress', to='school.student', verbose_name='الطالب')),
            ],
            options={
                'verbose_name': 'تقدم الطالب في الدرس',
                'verbose_name_plural': 'تقدم الطلاب في الدروس',
                'ordering': ['-last_activity_at', '-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='studentlessonprogress',
            constraint=models.UniqueConstraint(fields=('student', 'lesson'), name='unique_student_lesson_progress'),
        ),
    ]
