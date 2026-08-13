from django.db import models
from django.contrib.auth.models import User
from school.models import Class, Subject, Teacher


class LearningLesson(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('pending', 'بانتظار الاعتماد'),
        ('approved', 'معتمد'),
        ('published', 'منشور'),
        ('rejected', 'مرفوض'),
        ('archived', 'مؤرشف'),
    ]

    title = models.CharField('عنوان الدرس', max_length=200)
    description = models.TextField('وصف الدرس', blank=True)
    student_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='learning_lessons', verbose_name='الصف')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='learning_lessons', verbose_name='المادة')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='learning_lessons', verbose_name='المعلم')
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='draft')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='راجعه')
    review_note = models.TextField('ملاحظة المراجعة', blank=True, help_text='سبب الرفض إن وُجد')
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('آخر تعديل', auto_now=True)

    class Meta:
        verbose_name = 'درس مفتوح'
        verbose_name_plural = 'دروس التعلم المفتوح'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} - {self.student_class.name} - {self.subject.name}'

    @property
    def status_display_ar(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def is_visible_to_students(self):
        return self.status == 'published'


class LearningResource(models.Model):
    RESOURCE_TYPES = [
        ('video', 'فيديو'),
        ('presentation', 'عرض تقديمي'),
        ('exercise', 'تمرين'),
        ('homework', 'واجب'),
        ('summary', 'ملخص'),
        ('quiz', 'اختبار'),
        ('activity', 'نشاط'),
        ('lesson', 'درس'),
        ('link', 'رابط'),
        ('reading', 'قراءة'),
    ]

    lesson = models.ForeignKey(LearningLesson, on_delete=models.CASCADE, related_name='resources', verbose_name='الدرس')
    title = models.CharField('عنوان المورد', max_length=200)
    resource_type = models.CharField('النوع', max_length=20, choices=RESOURCE_TYPES)
    url = models.TextField('الرابط')
    description = models.CharField('وصف مختصر', max_length=500, blank=True)
    created_at = models.DateTimeField('تاريخ الإضافة', auto_now_add=True)

    class Meta:
        verbose_name = 'مورد تعليمي'
        verbose_name_plural = 'الموارد التعليمية'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.title} - {self.get_resource_type_display()}'

    @property
    def type_icon(self):
        icons = {
            'video': 'bi-play-circle-fill',
            'presentation': 'bi-easel-fill',
            'exercise': 'bi-pencil-square',
            'homework': 'bi-journal-check',
            'summary': 'bi-card-text',
            'quiz': 'bi-question-circle-fill',
            'activity': 'bi-lightbulb-fill',
            'lesson': 'bi-book-fill',
            'link': 'bi-link-45deg',
            'reading': 'bi-journal-text',
        }
        return icons.get(self.resource_type, 'bi-link-45deg')
