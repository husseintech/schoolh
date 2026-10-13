from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('school','0060_healthcommitteeofficialform'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name='VisitAssessmentReport',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('report_type',models.CharField(choices=[('primary','تقييم حصة للصفوف 1–4'),('upper','تقرير زيارة إشرافية للصف الخامس فأعلى')],max_length=20,verbose_name='نوع التقرير')),
        ('visit_date',models.DateField(verbose_name='تاريخ الزيارة')),('visit_number',models.CharField(blank=True,max_length=50,verbose_name='رقم الزيارة')),
        ('subject_area',models.CharField(blank=True,max_length=200,verbose_name='المبحث')),('lesson_topic',models.CharField(blank=True,max_length=300,verbose_name='موضوع الدرس')),
        ('class_name',models.CharField(blank=True,max_length=100,verbose_name='الصف')),('section',models.CharField(blank=True,max_length=50,verbose_name='الشعبة')),
        ('scores',models.JSONField(blank=True,default=dict,verbose_name='درجات المؤشرات')),('evidence',models.JSONField(blank=True,default=dict,verbose_name='الشواهد والملاحظات')),
        ('details',models.JSONField(blank=True,default=dict,verbose_name='تفاصيل التقرير')),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
        ('created_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='created_visit_assessment_reports',to=settings.AUTH_USER_MODEL,verbose_name='أنشئ بواسطة')),
        ('teacher',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='assessment_reports',to='school.teacher',verbose_name='المعلم'))],
        options={'verbose_name':'تقرير تقييم زيارة','verbose_name_plural':'تقارير تقييم الزيارات','ordering':['-visit_date','-updated_at']})]
