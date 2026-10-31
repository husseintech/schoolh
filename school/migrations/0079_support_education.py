from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('school', '0078_kindergarten_report_separate_fields')]
    operations = [
        migrations.AlterField(
            model_name='profile', name='role',
            field=models.CharField(choices=[('admin','مدير'),('vice_principal','نائب مدير'),('secretary','سكرتير'),('teacher','معلم'),('support_teacher','معلم مساند'),('student','طالب'),('warden','آذن')], default='student', max_length=20, verbose_name='الدور'),
        ),
        migrations.CreateModel(
            name='SupportLessonAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lesson_title', models.CharField(max_length=250, verbose_name='عنوان الدرس')),
                ('page_number', models.CharField(blank=True, max_length=40, verbose_name='رقم الصفحة')),
                ('required_work', models.TextField(verbose_name='المطلوب تنفيذه')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التكليف')),
                ('class_obj', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='support_assignments', to='school.class', verbose_name='الصف')),
                ('original_teacher', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='support_assignments', to='school.teacher', verbose_name='المعلم الأصيل')),
            ],
            options={'verbose_name':'تكليف تعليم مساند','verbose_name_plural':'تكليفات التعليم المساند','ordering':['-created_at','-id']},
        ),
        migrations.CreateModel(
            name='SupportLessonExecution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('execution_date', models.DateField(verbose_name='تاريخ التنفيذ')),
                ('lesson_period', models.PositiveSmallIntegerField(verbose_name='رقم الحصة')),
                ('notes', models.TextField(verbose_name='متابعة التنفيذ')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسجيل')),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='executions', to='school.supportlessonassignment', verbose_name='التكليف')),
                ('support_teacher', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='support_executions', to='school.teacher', verbose_name='المعلم المساند')),
            ],
            options={'verbose_name':'متابعة تنفيذ التعليم المساند','verbose_name_plural':'متابعات تنفيذ التعليم المساند','ordering':['-execution_date','-created_at']},
        ),
    ]
