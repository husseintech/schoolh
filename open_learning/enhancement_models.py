from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class GuardianStudentLink(models.Model):
    guardian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='open_learning_guardian_links',
        verbose_name='ولي الأمر',
    )
    student = models.ForeignKey(
        'school.Student',
        on_delete=models.CASCADE,
        related_name='open_learning_guardian_links',
        verbose_name='الطالب',
    )
    relation = models.CharField('صلة القرابة', max_length=50, default='ولي أمر')
    is_active = models.BooleanField('نشط', default=True)
    created_at = models.DateTimeField('تاريخ الربط', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['guardian', 'student'], name='unique_guardian_student_link')
        ]
        verbose_name = 'ربط ولي أمر بطالب'
        verbose_name_plural = 'روابط أولياء الأمور بالطلاب'

    def __str__(self):
        return f'{self.guardian.username} - {self.student.full_name}'


class LearningAchievement(models.Model):
    KIND_CHOICES = [
        ('lesson_complete', 'إكمال درس'),
        ('perfect_quiz', 'علامة كاملة في اختبار'),
        ('consistent', 'مواظبة تعليمية'),
    ]
    student = models.ForeignKey(
        'school.Student',
        on_delete=models.CASCADE,
        related_name='open_learning_achievements',
        verbose_name='الطالب',
    )
    lesson = models.ForeignKey(
        'open_learning.LearningLesson',
        on_delete=models.CASCADE,
        related_name='achievements',
        verbose_name='الدرس',
    )
    kind = models.CharField('نوع الإنجاز', max_length=30, choices=KIND_CHOICES)
    title = models.CharField('عنوان الإنجاز', max_length=200)
    description = models.CharField('الوصف', max_length=500, blank=True)
    awarded_at = models.DateTimeField('تاريخ الإنجاز', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'lesson', 'kind'], name='unique_student_lesson_achievement')
        ]
        ordering = ['-awarded_at']
        verbose_name = 'إنجاز تعلم'
        verbose_name_plural = 'إنجازات التعلم'


class RemediationPlan(models.Model):
    STATUS_CHOICES = [('active', 'نشطة'), ('completed', 'مكتملة')]
    student = models.ForeignKey(
        'school.Student',
        on_delete=models.CASCADE,
        related_name='open_learning_remediation_plans',
        verbose_name='الطالب',
    )
    lesson = models.ForeignKey(
        'open_learning.LearningLesson',
        on_delete=models.CASCADE,
        related_name='remediation_plans',
        verbose_name='الدرس',
    )
    quiz = models.ForeignKey(
        'open_learning.LessonQuiz',
        on_delete=models.CASCADE,
        related_name='remediation_plans',
        verbose_name='الاختبار',
        null=True,
        blank=True,
    )
    reason = models.CharField('سبب الخطة', max_length=300)
    recommendation = models.TextField('التوصية العلاجية')
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('آخر تحديث', auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'quiz'], name='unique_student_quiz_remediation')
        ]
        ordering = ['-updated_at']
        verbose_name = 'خطة علاجية'
        verbose_name_plural = 'الخطط العلاجية'


class LearningResourceFavorite(models.Model):
    student = models.ForeignKey(
        'school.Student',
        on_delete=models.CASCADE,
        related_name='open_learning_resource_favorites',
        verbose_name='الطالب',
    )
    resource = models.ForeignKey(
        'open_learning.LearningResourceLibrary',
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='المصدر',
    )
    created_at = models.DateTimeField('تاريخ الإضافة للمفضلة', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'resource'], name='unique_student_resource_favorite')
        ]
        verbose_name = 'مصدر مفضل'
        verbose_name_plural = 'المصادر المفضلة'


class LearningResourceRating(models.Model):
    student = models.ForeignKey(
        'school.Student',
        on_delete=models.CASCADE,
        related_name='open_learning_resource_ratings',
        verbose_name='الطالب',
    )
    resource = models.ForeignKey(
        'open_learning.LearningResourceLibrary',
        on_delete=models.CASCADE,
        related_name='ratings',
        verbose_name='المصدر',
    )
    rating = models.PositiveSmallIntegerField(
        'التقييم', validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    note = models.CharField('ملاحظة', max_length=300, blank=True)
    updated_at = models.DateTimeField('آخر تحديث', auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'resource'], name='unique_student_resource_rating')
        ]
        verbose_name = 'تقييم مصدر'
        verbose_name_plural = 'تقييمات المصادر'
