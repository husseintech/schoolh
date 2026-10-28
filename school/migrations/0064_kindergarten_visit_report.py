# Generated for kindergarten visit reports
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0075_exampaper_exam_direction'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='KindergartenVisitReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visit_date', models.DateField(default=django.utils.timezone.localdate, verbose_name='تاريخ الزيارة')),
                ('qualifications', models.TextField(blank=True, verbose_name='المؤهلات العلمية والمسلكية')),
                ('experience_years', models.TextField(blank=True, verbose_name='سنوات الخبرة')),
                ('daily_preparation', models.TextField(blank=True, verbose_name='التحضير اليومي')),
                ('activity', models.TextField(blank=True, verbose_name='النشاط')),
                ('activity_start', models.CharField(blank=True, max_length=30, verbose_name='بداية النشاط')),
                ('activity_end', models.CharField(blank=True, max_length=30, verbose_name='نهاية النشاط')),
                ('preparation', models.TextField(blank=True, verbose_name='التهيئة للنشاط')),
                ('objectives', models.TextField(blank=True, verbose_name='وضوح الأهداف')),
                ('teaching_aids', models.TextField(blank=True, verbose_name='الوسائل التعليمية المساندة')),
                ('aids_adequacy', models.TextField(blank=True, verbose_name='كفاية الوسائل ومناسبتها')),
                ('method', models.TextField(blank=True, verbose_name='الأسلوب المتبع')),
                ('teaching_style', models.CharField(blank=True, max_length=30, verbose_name='نمط التعليم')),
                ('children_interaction', models.TextField(blank=True, verbose_name='تفاعل الأطفال')),
                ('individual_differences', models.TextField(blank=True, verbose_name='مراعاة الفروق الفردية')),
                ('group_work', models.TextField(blank=True, verbose_name='العمل ضمن مجموعات')),
                ('goals_achieved', models.TextField(blank=True, verbose_name='مدى تحقق الأهداف')),
                ('strengths', models.TextField(blank=True, verbose_name='نقاط مميزة لدى المربية')),
                ('improvement_notes', models.TextField(blank=True, verbose_name='ملاحظات لتطوير عمل المربية')),
                ('principal_signature', models.CharField(blank=True, max_length=200, verbose_name='توقيع مدير المدرسة')),
                ('teacher_signature', models.CharField(blank=True, max_length=200, verbose_name='توقيع المربية')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kindergarten_visit_reports', to='school.teacher', verbose_name='المربية')),
            ],
            options={'verbose_name': 'تقرير زيارة مربية رياض الأطفال', 'verbose_name_plural': 'تقارير زيارات مربيات رياض الأطفال', 'ordering': ['-visit_date', '-created_at']},
        ),
        migrations.CreateModel(
            name='KindergartenVisitAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='kindergarten_visit_reports/%Y/%m/', verbose_name='الملف المرفق')),
                ('original_name', models.CharField(blank=True, max_length=255, verbose_name='اسم الملف')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='school.kindergartenvisitreport')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'مرفق تقرير زيارة تمهيدي', 'verbose_name_plural': 'مرفقات تقارير زيارات تمهيدي'},
        ),
    ]
