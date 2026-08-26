import json
from datetime import timedelta

from django.db import models
from django.core.signing import Signer, BadSignature
from django.utils import timezone
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
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='أضافه')
    source_kind = models.CharField('مصدر المورد', max_length=20, choices=[('link', 'رابط خارجي'), ('google_drive', 'Google Drive')], default='link', blank=True)
    google_drive_file_id = models.CharField('معرّف ملف Google Drive', max_length=200, blank=True)
    google_drive_url = models.TextField('رابط Google Drive', blank=True)
    file_name = models.CharField('اسم الملف', max_length=300, blank=True)
    file_type = models.CharField('نوع الملف', max_length=100, blank=True)
    file_size = models.PositiveIntegerField('حجم الملف (بايت)', null=True, blank=True)
    storage_provider = models.CharField('مزوّد التخزين', max_length=20, choices=[('', '—'), ('google_drive', 'Google Drive')], blank=True, default='')
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


class GoogleDriveToken(models.Model):
    token_json = models.TextField('بيانات الرمز المشفّرة', blank=True,
                                  help_text='رمز الوصول ورمز التحديث مشفّران (موقّعان) ولا يظهران في الكود أو نظام الملفات')
    token_expiry = models.DateTimeField('انتهاء صلاحية رمز الوصول', null=True, blank=True)
    scope = models.TextField('النطاق المصرّح به', blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('آخر تعديل', auto_now=True)

    class Meta:
        verbose_name = 'رمز Google Drive'
        verbose_name_plural = 'رموز Google Drive'

    def __str__(self):
        return 'Google Drive Token'

    def set_tokens(self, token_dict):
        signer = Signer()
        self.token_json = signer.sign(json.dumps(token_dict, ensure_ascii=False))
        self.token_expiry = None
        if token_dict.get('expires_in'):
            try:
                self.token_expiry = timezone.now() + timedelta(seconds=int(token_dict['expires_in']))
            except (TypeError, ValueError):
                self.token_expiry = None
        self.scope = token_dict.get('scope', '')

    def get_tokens(self):
        if not self.token_json:
            return {}
        try:
            return json.loads(Signer().unsign(self.token_json))
        except (BadSignature, json.JSONDecodeError):
            return {}


PLAN_WEEKDAYS = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس']


class WeeklyPlan(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('completed', 'مكتملة'),
        ('sent', 'مرسلة للمتابعة'),
        ('reviewed', 'تمت مراجعتها'),
        ('needs_improvement', 'تحتاج تحسين'),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='weekly_plans', verbose_name='المعلم')
    student_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='weekly_plans', verbose_name='الصف')
    week_start = models.DateField('بداية الأسبوع')
    week_end = models.DateField('نهاية الأسبوع')
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField('تاريخ الإرسال', null=True, blank=True)
    reviewed_at = models.DateTimeField('تاريخ المراجعة', null=True, blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('آخر تعديل', auto_now=True)

    class Meta:
        verbose_name = 'خطة أسبوعية'
        verbose_name_plural = 'الخطط الأسبوعية'
        ordering = ['-week_start']

    def __str__(self):
        return f'خطة {self.teacher.full_name} - {self.student_class.name} - {self.week_start}'

    @property
    def is_editable(self):
        return self.status in ('draft', 'needs_improvement')

    @property
    def is_submitted(self):
        return self.status in ('sent', 'reviewed', 'needs_improvement')


class WeeklyPlanDay(models.Model):
    weekly_plan = models.ForeignKey(WeeklyPlan, on_delete=models.CASCADE, related_name='days', verbose_name='الخطة')
    day_of_week = models.CharField('يوم الأسبوع', max_length=20, choices=[(d, d) for d in PLAN_WEEKDAYS])
    date = models.DateField('التاريخ')
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='المادة')
    lesson = models.ForeignKey(LearningLesson, on_delete=models.SET_NULL, null=True, blank=True, related_name='plan_days', verbose_name='الدرس')
    lesson_title = models.CharField('عنوان الدرس', max_length=200, blank=True)
    objectives = models.TextField('الأهداف', blank=True)
    homework = models.TextField('الواجبات', blank=True)
    notes = models.TextField('ملاحظات', blank=True)
    order = models.PositiveSmallIntegerField('الترتيب', default=0)

    class Meta:
        verbose_name = 'يوم في الخطة الأسبوعية'
        verbose_name_plural = 'أيام الخطة الأسبوعية'
        ordering = ['order', 'date']

    def __str__(self):
        return f'{self.day_of_week} - {self.date}'

    @property
    def linked_resources(self):
        if self.lesson_id:
            return self.lesson.resources.all()
        return []


QUALITY_AXES = [
    ('عنوان الدرس', 'واضح ومرتبط بالمحتوى والأهداف التعليمية.'),
    ('عنوان الدرس', 'مناسب لخصائص الطلبة ومرحلتهم العمرية.'),
    ('الأهداف التعليمية', 'مصاغة بلغة واضحة ومفهومة للطالب وولي الأمر.'),
    ('الأهداف التعليمية', 'مناسبة للمستوى النمائي والمعرفي للطلبة.'),
    ('الأهداف التعليمية', 'قابلة للتحقق والقياس من خلال المهمات التعليمية.'),
    ('مصادر التعليم المفتوحة', 'مرتبطة بالأهداف التعليمية وتدعم تحقيقها.'),
    ('مصادر التعليم المفتوحة', 'جاذبة لانتباه الطلبة.'),
    ('مصادر التعليم المفتوحة', 'آمنة وموثوقة وملائمة لعمر الطلبة.'),
    ('مصادر التعليم المفتوحة', 'تتضمن بدائل ورقية أو ملموسة عند الحاجة.'),
    ('المهمات والواجبات', 'واضحة ومحددة ويمكن للطالب تنفيذها.'),
    ('المهمات والواجبات', 'تراعي الوقت والجهد المناسبين للطلبة.'),
    ('المهمات والواجبات', 'تعزز مشاركة الأسرة دون تحميلها عبئاً تعليمياً.'),
    ('النشر والتواصل', 'نُشرت الخطة قبل بدء الأسبوع بوقت كافٍ.'),
    ('النشر والتواصل', 'جميع الروابط والمرفقات تعمل بصورة صحيحة.'),
    ('النشر والتواصل', 'الخطة مكتوبة بلغة واضحة وسهلة لأولياء الأمور.'),
]


class WeeklyPlanReview(models.Model):
    STATUS_CHOICES = [
        ('needs_improvement', 'تحتاج تحسين'),
        ('approved', 'معتمدة'),
    ]

    weekly_plan = models.OneToOneField(WeeklyPlan, on_delete=models.CASCADE, related_name='review', verbose_name='الخطة')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='راجعها')
    status = models.CharField('النتيجة', max_length=20, choices=STATUS_CHOICES, default='needs_improvement')
    general_note = models.TextField('ملاحظة عامة', blank=True)
    reviewed_at = models.DateTimeField('تاريخ المراجعة', auto_now=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        verbose_name = 'مراجعة الخطة الأسبوعية'
        verbose_name_plural = 'مراجعات الخطط الأسبوعية'

    def __str__(self):
        return f'مراجعة {self.weekly_plan}'

    @property
    def total(self):
        return self.items.count()

    @property
    def met_count(self):
        return self.items.filter(is_met=True).count()

    @property
    def needs_count(self):
        return self.items.filter(needs_improvement=True).count()

    @property
    def percentage(self):
        if not self.total:
            return 0
        return round(self.met_count * 100 / self.total)


class WeeklyPlanReviewItem(models.Model):
    review = models.ForeignKey(WeeklyPlanReview, on_delete=models.CASCADE, related_name='items', verbose_name='المراجعة')
    axis = models.CharField('المحور', max_length=100)
    indicator = models.TextField('مؤشر الجودة')
    is_met = models.BooleanField('متحقق', default=False)
    needs_improvement = models.BooleanField('يحتاج تحسين', default=False)
    note = models.TextField('ملاحظات المدير', blank=True)
    order = models.PositiveSmallIntegerField('الترتيب', default=0)

    class Meta:
        verbose_name = 'مؤشر جودة'
        verbose_name_plural = 'مؤشرات الجودة'
        ordering = ['order']

    def __str__(self):
        return f'{self.axis} - {self.indicator[:40]}'


class TeacherPlan(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='teacher_plans', verbose_name='المعلم')
    student_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='teacher_plans', verbose_name='الصف')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='teacher_plans', verbose_name='المادة')
    note = models.CharField('ملاحظة', max_length=300, blank=True)
    created_at = models.DateTimeField('تاريخ الرفع', auto_now_add=True)

    class Meta:
        verbose_name = 'خطة معلم مرفوعة'
        verbose_name_plural = 'خطط المعلمين المرفوعة'
        ordering = ['-created_at']

    def __str__(self):
        return f'خطة {self.teacher.full_name} - {self.student_class.name} - {self.subject.name}'


class TeacherPlanFile(models.Model):
    plan = models.ForeignKey(TeacherPlan, on_delete=models.CASCADE, related_name='files', verbose_name='الخطة')
    file_name = models.CharField('اسم الملف', max_length=300, blank=True)
    file_type = models.CharField('نوع الملف', max_length=100, blank=True)
    google_drive_file_id = models.CharField('معرّف ملف Google Drive', max_length=200, blank=True)
    google_drive_url = models.TextField('رابط الملف في Drive', blank=True)
    order = models.PositiveSmallIntegerField('الترتيب', default=0)
    uploaded_at = models.DateTimeField('تاريخ الرفع', auto_now_add=True)

    class Meta:
        verbose_name = 'ملف خطة معلم'
        verbose_name_plural = 'ملفات خطط المعلمين'
        ordering = ['order', 'uploaded_at']

    def __str__(self):
        return self.file_name or 'ملف'
