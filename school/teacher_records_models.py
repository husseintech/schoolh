from django.db import models
from django.contrib.auth.models import User


class ClassSubjectMapping(models.Model):
    student_class = models.ForeignKey('school.Class', on_delete=models.CASCADE, related_name='subject_mappings', verbose_name='الصف')
    subject = models.ForeignKey('school.Subject', on_delete=models.CASCADE, related_name='class_mappings', verbose_name='المبحث')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_class_subject_mappings')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['student_class', 'subject'], name='unique_class_subject_mapping')]
        ordering = ['student_class__name', 'subject__name']
        verbose_name = 'مادة صف'
        verbose_name_plural = 'مواد الصفوف'

    def __str__(self):
        return f'{self.student_class} - {self.subject}'


class CurriculumProgressRecord(models.Model):
    teacher = models.ForeignKey('school.Teacher', on_delete=models.CASCADE, related_name='curriculum_progress_records', verbose_name='المعلم')
    subject = models.ForeignKey('school.Subject', on_delete=models.PROTECT, related_name='curriculum_progress_records', verbose_name='المبحث')
    student_class = models.ForeignKey('school.Class', on_delete=models.PROTECT, related_name='curriculum_progress_records', verbose_name='الصف')
    student_classes = models.ManyToManyField('school.Class', blank=True, related_name='curriculum_multi_progress_records', verbose_name='الصفوف')
    record_date = models.DateField('التاريخ')
    academic_year = models.CharField('العام الدراسي', max_length=20)
    assigned_pages = models.PositiveIntegerField('الصفحات المقررة', default=0)
    completed_pages = models.PositiveIntegerField('الصفحات المقطوعة', default=0)
    notes = models.TextField('ملاحظات', blank=True)
    principal_notes = models.TextField('ملاحظات مدير/ة المدرسة', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_curriculum_records')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def remaining_pages(self):
        return max(self.assigned_pages - self.completed_pages, 0)

    @property
    def selected_classes(self):
        classes = list(self.student_classes.all())
        return classes if classes else ([self.student_class] if self.student_class_id else [])

    @property
    def class_names(self):
        return '، '.join(c.name for c in self.selected_classes)

    @property
    def students_count(self):
        ids = [c.id for c in self.selected_classes]
        if not ids:
            return 0
        from .models import Student
        return Student.objects.filter(student_class_id__in=ids).count()

    class Meta:
        ordering = ['-record_date', '-id']
        verbose_name = 'سجل ما قطع من المنهاج'
        verbose_name_plural = 'سجلات ما قطع من المنهاج'


class TeacherTrainingRecord(models.Model):
    teacher = models.ForeignKey('school.Teacher', on_delete=models.CASCADE, related_name='training_records', verbose_name='المعلم')
    course_date = models.DateField('اليوم والتاريخ')
    course_name = models.CharField('اسم الدورة', max_length=250)
    course_location = models.CharField('مكان الدورة', max_length=250, blank=True)
    target_group = models.TextField('الفئة المستهدفة التي تخدمها الدورة', blank=True)
    outcomes = models.TextField('أهم نتاجات الدورة', blank=True)
    notes = models.TextField('ملاحظات', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_training_records')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-course_date', '-id']
        verbose_name = 'سجل دورة معلم'
        verbose_name_plural = 'سجل الدورات'
