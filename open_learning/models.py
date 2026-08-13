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

    AI_STATUS_CHOICES = [
        ('none', 'بدون محتوى ذكي'),
        ('pending', 'بانتظار مراجعة المعلم'),
        ('approved', 'معتمد'),
    ]

    title = models.CharField('عنوان الدرس', max_length=200)
    description = models.TextField('وصف الدرس', blank=True)
    student_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='learning_lessons', verbose_name='الصف')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='learning_lessons', verbose_name='المادة')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='learning_lessons', verbose_name='المعلم')
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='draft')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='راجعه')
    review_note = models.TextField('ملاحظة المراجعة', blank=True, help_text='سبب الرفض إن وُجد')
    ai_status = models.CharField('حالة المحتوى الذكي', max_length=20, choices=AI_STATUS_CHOICES, default='none')
    ai_payload = models.JSONField('المحتوى الذكي', default=dict, blank=True, help_text='أقسام المحتوى المولّد بالذكاء الاصطناعي')
    ai_generated_at = models.DateTimeField('تاريخ توليد المحتوى الذكي', null=True, blank=True)
    ai_reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='راجع المحتوى الذكي')
    ai_review_note = models.TextField('ملاحظة مراجعة المحتوى الذكي', blank=True)
    content_hash = models.CharField('بصمة المحتوى', max_length=64, blank=True, help_text='بصمة الصف+المادة+العنوان+الوصف لتجنب إعادة التوليد')
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

    @property
    def ai_visible_to_students(self):
        return self.status == 'published' and self.ai_status == 'approved' and bool(self.ai_payload)


class LearningResourceLibrary(models.Model):
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
        ('image', 'صورة'),
        ('simulation', 'محاكاة'),
        ('experiment', 'تجربة'),
    ]

    STATUS_CHOICES = [
        ('pending', 'بانتظار الاعتماد'),
        ('approved', 'معتمد'),
        ('archived', 'مؤرشف'),
    ]

    LANGUAGE_CHOICES = [
        ('ar', 'عربي'),
        ('en', 'إنجليزي'),
        ('other', 'أخرى'),
    ]

    title = models.CharField('عنوان المصدر', max_length=300)
    url = models.TextField('الرابط')
    normalized_url = models.CharField('رابط موحّد', max_length=500, unique=True)
    resource_type = models.CharField('النوع', max_length=20, choices=RESOURCE_TYPES)
    source_name = models.CharField('اسم المصدر', max_length=200, blank=True)
    language = models.CharField('اللغة', max_length=10, choices=LANGUAGE_CHOICES, default='ar')
    relevance_score = models.PositiveIntegerField('درجة الملاءمة', null=True, blank=True)
    grade_level = models.CharField('الصف الدراسي', max_length=100, blank=True)
    description = models.CharField('وصف مختصر', max_length=500, blank=True)
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='pending')
    is_ai_generated = models.BooleanField('أُضيف بواسطة الذكاء الاصطناعي', default=False)
    ai_generated_at = models.DateTimeField('تاريخ الإضافة الذكية', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='أضافه')
    created_at = models.DateTimeField('تاريخ الإضافة', auto_now_add=True)

    class Meta:
        verbose_name = 'مصدر في مكتبة التعلم'
        verbose_name_plural = 'مكتبة مصادر التعلم'
        ordering = ['-relevance_score', '-created_at']

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
            'image': 'bi-image-fill',
            'simulation': 'bi-diagram-3-fill',
            'experiment': 'bi-flask-fill',
        }
        return icons.get(self.resource_type, 'bi-link-45deg')


class LearningResource(models.Model):
    RESOURCE_TYPES = LearningResourceLibrary.RESOURCE_TYPES
    STATUS_CHOICES = [
        ('pending', 'بانتظار الاعتماد'),
        ('approved', 'معتمد'),
        ('archived', 'مؤرشف'),
    ]
    LANGUAGE_CHOICES = LearningResourceLibrary.LANGUAGE_CHOICES

    lesson = models.ForeignKey(LearningLesson, on_delete=models.CASCADE, related_name='resources', verbose_name='الدرس')
    title = models.CharField('عنوان المورد', max_length=200)
    resource_type = models.CharField('النوع', max_length=20, choices=RESOURCE_TYPES)
    url = models.TextField('الرابط')
    description = models.CharField('وصف مختصر', max_length=500, blank=True)
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='approved')
    language = models.CharField('اللغة', max_length=10, choices=LANGUAGE_CHOICES, default='ar')
    source_name = models.CharField('اسم المصدر', max_length=200, blank=True)
    relevance_score = models.PositiveIntegerField('درجة الملاءمة', null=True, blank=True)
    is_ai_generated = models.BooleanField('أُضيف بواسطة الذكاء الاصطناعي', default=False)
    ai_generated_at = models.DateTimeField('تاريخ الإضافة الذكية', null=True, blank=True)
    library = models.ForeignKey(LearningResourceLibrary, on_delete=models.SET_NULL, null=True, blank=True, related_name='lesson_links', verbose_name='المصدر المركزي')
    created_at = models.DateTimeField('تاريخ الإضافة', auto_now_add=True)

    class Meta:
        verbose_name = 'مورد تعليمي'
        verbose_name_plural = 'الموارد التعليمية'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.title} - {self.get_resource_type_display()}'

    @property
    def type_icon(self):
        return self.library.type_icon if self.library else {
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
            'image': 'bi-image-fill',
            'simulation': 'bi-diagram-3-fill',
            'experiment': 'bi-flask-fill',
        }.get(self.resource_type, 'bi-link-45deg')


class AIUsageLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_usage_logs', verbose_name='المستخدم')
    lesson = models.ForeignKey(LearningLesson, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_usage_logs', verbose_name='الدرس')
    operation = models.CharField('العملية', max_length=50)
    provider = models.CharField('المزوّد', max_length=50, blank=True)
    model = models.CharField('النموذج', max_length=100, blank=True)
    success = models.BooleanField('نجحت', default=True)
    error = models.TextField('الخطأ', blank=True)
    estimated_tokens = models.PositiveIntegerField('الرموز المقدّرة', null=True, blank=True)
    duration_ms = models.PositiveIntegerField('المدة بالمللي ثانية', null=True, blank=True)
    created_at = models.DateTimeField('التاريخ', auto_now_add=True)

    class Meta:
        verbose_name = 'سجل استخدام الذكاء الاصطناعي'
        verbose_name_plural = 'سجل استخدام الذكاء الاصطناعي'
        ordering = ['-created_at']

    OPERATION_LABELS = {
        'generate_content': 'توليد محتوى',
        'regenerate_questions': 'توليد أسئلة',
        'regenerate_explanation': 'توليد شرح',
        'regenerate_activities': 'اقتراح أنشطة',
        'search_resources': 'بحث ذكي عن مصادر',
        'update_resources': 'تحديث المصادر',
        'cache_hit': 'استخدام مخزّن',
    }

    @property
    def operation_label(self):
        return self.OPERATION_LABELS.get(self.operation, self.operation)

    def __str__(self):
        return f'{self.operation} - {self.created_at}'
