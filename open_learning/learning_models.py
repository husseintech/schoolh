from django.db import models


class LessonActivity(models.Model):
    TYPE_CHOICES = [
        ('practice', 'تدريب'),
        ('discussion', 'مناقشة'),
        ('exploration', 'استكشاف'),
        ('project', 'مشروع قصير'),
    ]
    lesson = models.ForeignKey('open_learning.LearningLesson', on_delete=models.CASCADE, related_name='learning_activities', verbose_name='الدرس')
    title = models.CharField('عنوان النشاط', max_length=200)
    instructions = models.TextField('تعليمات النشاط')
    activity_type = models.CharField('نوع النشاط', max_length=20, choices=TYPE_CHOICES, default='practice')
    is_required = models.BooleanField('إلزامي', default=False)
    order = models.PositiveSmallIntegerField('الترتيب', default=0)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'نشاط درس'
        verbose_name_plural = 'أنشطة الدروس'

    def __str__(self):
        return f'{self.lesson.title} - {self.title}'


class StudentActivityCompletion(models.Model):
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='open_learning_activity_completions', verbose_name='الطالب')
    activity = models.ForeignKey(LessonActivity, on_delete=models.CASCADE, related_name='completions', verbose_name='النشاط')
    completed_at = models.DateTimeField('تاريخ الإكمال', auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['student', 'activity'], name='unique_student_activity_completion')]
        verbose_name = 'إكمال نشاط'
        verbose_name_plural = 'إكمال الأنشطة'


class LessonQuiz(models.Model):
    lesson = models.ForeignKey('open_learning.LearningLesson', on_delete=models.CASCADE, related_name='learning_quizzes', verbose_name='الدرس')
    title = models.CharField('عنوان الاختبار', max_length=200)
    instructions = models.TextField('التعليمات', blank=True)
    is_published = models.BooleanField('منشور للطلاب', default=False)
    passing_score = models.PositiveSmallIntegerField('نسبة النجاح', default=50)
    max_attempts = models.PositiveSmallIntegerField('عدد المحاولات', default=2)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'اختبار درس'
        verbose_name_plural = 'اختبارات الدروس'

    def __str__(self):
        return f'{self.lesson.title} - {self.title}'


class QuizQuestion(models.Model):
    TYPE_CHOICES = [('mcq', 'اختيار من متعدد'), ('true_false', 'صح/خطأ')]
    quiz = models.ForeignKey(LessonQuiz, on_delete=models.CASCADE, related_name='questions', verbose_name='الاختبار')
    text = models.TextField('السؤال')
    question_type = models.CharField('نوع السؤال', max_length=20, choices=TYPE_CHOICES, default='mcq')
    options = models.JSONField('الخيارات', default=list, blank=True)
    correct_answer = models.CharField('الإجابة الصحيحة', max_length=300)
    points = models.PositiveSmallIntegerField('العلامة', default=1)
    order = models.PositiveSmallIntegerField('الترتيب', default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'سؤال اختبار'
        verbose_name_plural = 'أسئلة الاختبارات'


class QuizAttempt(models.Model):
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='open_learning_quiz_attempts', verbose_name='الطالب')
    quiz = models.ForeignKey(LessonQuiz, on_delete=models.CASCADE, related_name='attempts', verbose_name='الاختبار')
    score = models.DecimalField('العلامة', max_digits=7, decimal_places=2, default=0)
    max_score = models.DecimalField('العلامة الكاملة', max_digits=7, decimal_places=2, default=0)
    percentage = models.DecimalField('النسبة', max_digits=5, decimal_places=2, default=0)
    passed = models.BooleanField('ناجح', default=False)
    submitted_at = models.DateTimeField('تاريخ التسليم', auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'محاولة اختبار'
        verbose_name_plural = 'محاولات الاختبارات'


class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers', verbose_name='المحاولة')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='answers', verbose_name='السؤال')
    answer = models.CharField('الإجابة', max_length=500, blank=True)
    is_correct = models.BooleanField('صحيحة', default=False)
    awarded_points = models.DecimalField('العلامة المحتسبة', max_digits=6, decimal_places=2, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['attempt', 'question'], name='unique_attempt_question_answer')]
        verbose_name = 'إجابة اختبار'
        verbose_name_plural = 'إجابات الاختبارات'


class LessonAssignment(models.Model):
    lesson = models.ForeignKey('open_learning.LearningLesson', on_delete=models.CASCADE, related_name='learning_assignments', verbose_name='الدرس')
    title = models.CharField('عنوان الواجب', max_length=200)
    instructions = models.TextField('التعليمات')
    due_at = models.DateTimeField('موعد التسليم', null=True, blank=True)
    points = models.PositiveSmallIntegerField('العلامة', default=10)
    is_published = models.BooleanField('منشور للطلاب', default=False)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'واجب درس'
        verbose_name_plural = 'واجبات الدروس'


class AssignmentSubmission(models.Model):
    STATUS_CHOICES = [('submitted', 'تم التسليم'), ('reviewed', 'تمت المراجعة')]
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='open_learning_assignment_submissions', verbose_name='الطالب')
    assignment = models.ForeignKey(LessonAssignment, on_delete=models.CASCADE, related_name='submissions', verbose_name='الواجب')
    answer_text = models.TextField('الإجابة', blank=True)
    answer_link = models.URLField('رابط إضافي', blank=True, max_length=600)
    submitted_at = models.DateTimeField('تاريخ التسليم', auto_now=True)
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='submitted')
    grade = models.DecimalField('العلامة', max_digits=6, decimal_places=2, null=True, blank=True)
    feedback = models.TextField('ملاحظة المعلم', blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['student', 'assignment'], name='unique_student_assignment_submission')]
        ordering = ['-submitted_at']
        verbose_name = 'تسليم واجب'
        verbose_name_plural = 'تسليمات الواجبات'


class OpenResourceMetadata(models.Model):
    LICENSE_CHOICES = [
        ('cc0', 'CC0'), ('cc_by', 'CC BY'), ('cc_by_sa', 'CC BY-SA'),
        ('cc_by_nc', 'CC BY-NC'), ('public_domain', 'ملكية عامة'), ('unknown', 'غير محدد'),
    ]
    library = models.OneToOneField('open_learning.LearningResourceLibrary', on_delete=models.CASCADE, related_name='open_metadata', verbose_name='المصدر')
    license_type = models.CharField('الترخيص', max_length=20, choices=LICENSE_CHOICES, default='unknown')
    author = models.CharField('المؤلف/الجهة', max_length=250, blank=True)
    attribution = models.TextField('صيغة النسبة للمصدر', blank=True)
    source_url = models.URLField('رابط المصدر الأصلي', blank=True, max_length=700)
    verified_open_license = models.BooleanField('تم التحقق من الترخيص المفتوح', default=False)
    verified_at = models.DateTimeField('تاريخ التحقق', null=True, blank=True)

    class Meta:
        verbose_name = 'بيانات ترخيص مصدر مفتوح'
        verbose_name_plural = 'بيانات تراخيص المصادر المفتوحة'
