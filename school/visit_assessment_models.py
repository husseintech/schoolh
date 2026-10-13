from django.conf import settings
from django.db import models
from .models import Teacher

class VisitAssessmentReport(models.Model):
    TYPE_CHOICES = [('primary','تقييم حصة للصفوف 1–4'),('upper','تقرير زيارة إشرافية للصف الخامس فأعلى')]
    teacher = models.ForeignKey(Teacher,on_delete=models.CASCADE,related_name='assessment_reports',verbose_name='المعلم')
    report_type = models.CharField('نوع التقرير',max_length=20,choices=TYPE_CHOICES)
    visit_date = models.DateField('تاريخ الزيارة')
    visit_number = models.CharField('رقم الزيارة',max_length=50,blank=True)
    subject_area = models.CharField('المبحث',max_length=200,blank=True)
    lesson_topic = models.CharField('موضوع الدرس',max_length=300,blank=True)
    class_name = models.CharField('الصف',max_length=100,blank=True)
    section = models.CharField('الشعبة',max_length=50,blank=True)
    scores = models.JSONField('درجات المؤشرات',default=dict,blank=True)
    evidence = models.JSONField('الشواهد والملاحظات',default=dict,blank=True)
    details = models.JSONField('تفاصيل التقرير',default=dict,blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='created_visit_assessment_reports',verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name='تقرير تقييم زيارة'
        verbose_name_plural='تقارير تقييم الزيارات'
        ordering=['-visit_date','-updated_at']
    def __str__(self):
        return f'{self.get_report_type_display()} - {self.teacher.full_name} - {self.visit_date}'
