from django.db import models
from django.utils import timezone


class StudentLessonProgress(models.Model):
    STATUS_NOT_STARTED = 'not_started'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'

    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, 'لم يبدأ'),
        (STATUS_IN_PROGRESS, 'قيد التعلم'),
        (STATUS_COMPLETED, 'مكتمل'),
    ]

    student = models.ForeignKey(
        'school.Student',
        on_delete=models.CASCADE,
        related_name='open_learning_progress',
        verbose_name='الطالب',
    )
    lesson = models.ForeignKey(
        'open_learning.LearningLesson',
        on_delete=models.CASCADE,
        related_name='student_progress',
        verbose_name='الدرس',
    )
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default=STATUS_NOT_STARTED)
    first_started_at = models.DateTimeField('أول بدء', null=True, blank=True)
    last_activity_at = models.DateTimeField('آخر نشاط', null=True, blank=True)
    completed_at = models.DateTimeField('تاريخ الإكمال', null=True, blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('آخر تحديث', auto_now=True)

    class Meta:
        verbose_name = 'تقدم الطالب في الدرس'
        verbose_name_plural = 'تقدم الطلاب في الدروس'
        ordering = ['-last_activity_at', '-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['student', 'lesson'], name='unique_student_lesson_progress'),
        ]

    def __str__(self):
        return f'{self.student.full_name} - {self.lesson.title} - {self.get_status_display()}'

    def mark_started(self):
        now = timezone.now()
        if not self.first_started_at:
            self.first_started_at = now
        if self.status == self.STATUS_NOT_STARTED:
            self.status = self.STATUS_IN_PROGRESS
        self.last_activity_at = now
        self.save(update_fields=['first_started_at', 'status', 'last_activity_at', 'updated_at'])

    def mark_completed(self):
        now = timezone.now()
        if not self.first_started_at:
            self.first_started_at = now
        self.status = self.STATUS_COMPLETED
        self.last_activity_at = now
        self.completed_at = now
        self.save(update_fields=['first_started_at', 'status', 'last_activity_at', 'completed_at', 'updated_at'])
