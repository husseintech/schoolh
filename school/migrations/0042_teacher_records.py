from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('school', '0041_schoolpublicsettings')]

    operations = [
        migrations.CreateModel(
            name='CurriculumProgressRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('record_date', models.DateField(verbose_name='التاريخ')),
                ('academic_year', models.CharField(max_length=20, verbose_name='العام الدراسي')),
                ('assigned_pages', models.PositiveIntegerField(default=0, verbose_name='الصفحات المقررة')),
                ('completed_pages', models.PositiveIntegerField(default=0, verbose_name='الصفحات المقطوعة')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('principal_notes', models.TextField(blank=True, verbose_name='ملاحظات مدير/ة المدرسة')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_curriculum_records', to='auth.user')),
                ('student_class', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='curriculum_progress_records', to='school.class', verbose_name='الصف')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='curriculum_progress_records', to='school.subject', verbose_name='المبحث')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='curriculum_progress_records', to='school.teacher', verbose_name='المعلم')),
            ], options={'ordering':['-record_date','-id'], 'verbose_name':'سجل ما قطع من المنهاج','verbose_name_plural':'سجلات ما قطع من المنهاج'}),
        migrations.CreateModel(
            name='TeacherTrainingRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('course_date', models.DateField(verbose_name='اليوم والتاريخ')),
                ('course_name', models.CharField(max_length=250, verbose_name='اسم الدورة')),
                ('course_location', models.CharField(blank=True, max_length=250, verbose_name='مكان الدورة')),
                ('target_group', models.TextField(blank=True, verbose_name='الفئة المستهدفة التي تخدمها الدورة')),
                ('outcomes', models.TextField(blank=True, verbose_name='أهم نتاجات الدورة')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_training_records', to='auth.user')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='training_records', to='school.teacher', verbose_name='المعلم')),
            ], options={'ordering':['-course_date','-id'], 'verbose_name':'سجل دورة معلم','verbose_name_plural':'سجل الدورات'}),
    ]
