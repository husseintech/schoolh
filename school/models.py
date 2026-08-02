from django.db import models
from django.contrib.auth.models import User
from datetime import date, datetime
from django.utils import timezone


def has_perm(user, module, action):
    if user.profile.role == 'admin':
        return True
    try:
        perms = user.custom_permissions
        return action in perms.permissions.get(module, [])
    except User.custom_permissions.RelatedObjectDoesNotExist:
        return False


def can_view(user, module):
    return has_perm(user, module, 'view')


class Profile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'مدير'),
        ('vice_principal', 'نائب مدير'),
        ('secretary', 'سكرتير'),
        ('teacher', 'معلم'),
        ('student', 'طالب'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField('الدور', max_length=20, choices=ROLE_CHOICES, default='student')
    phone = models.CharField('رقم الهاتف', max_length=20, blank=True)

    def __str__(self):
        return f'{self.user.username} - {self.get_role_display()}'


# Default permissions by role
DEFAULT_PERMISSIONS = {
    'admin': {
        'students': ['view', 'add', 'edit', 'delete', 'import', 'export'],
        'teachers': ['view', 'add', 'edit', 'delete', 'notes'],
        'classes': ['view', 'add', 'delete'],
        'subjects': ['view', 'add', 'delete'],
        'announcements': ['view', 'add', 'delete'],
        'agenda': ['view', 'add', 'complete', 'delete'],
        'leaves': ['view', 'add', 'delete'],
        'levels': ['view', 'add'],
        'exams': ['view', 'add'],
        'messages': ['view', 'send'],
        'reports': ['view'],
        'settings': ['whatsapp', 'accounts', 'links'],
        'notes': ['view', 'add'],
        'lateness': ['view', 'add'],
        'meetings': ['view', 'add'],
        'absence': ['view', 'add'],
        'schedule': ['view', 'add'],
        'survey': ['view', 'add'],
    },
    'vice_principal': {
        'students': ['view', 'add', 'edit', 'import', 'export'],
        'teachers': ['view', 'notes'],
        'classes': ['view'],
        'subjects': ['view'],
        'announcements': ['view', 'add', 'delete'],
        'agenda': ['view', 'add', 'complete'],
        'leaves': ['view', 'add'],
        'levels': ['view', 'add'],
        'exams': ['view', 'add'],
        'messages': ['view', 'send'],
        'reports': ['view'],
        'settings': [],
        'notes': ['view', 'add'],
        'absence': ['view', 'add'],
    },
    'secretary': {        'students': ['view', 'add', 'edit', 'import', 'export'],
        'teachers': ['view'],
        'classes': ['view'],
        'subjects': ['view'],
        'announcements': ['view', 'add'],
        'agenda': ['view'],
        'leaves': ['view', 'add', 'delete'],
        'levels': ['view'],
        'exams': ['view'],
        'messages': ['view'],
        'reports': [],
        'settings': [],
        'notes': ['view', 'add'],
        'lateness': ['view', 'add'],
        'absence': ['view', 'add'],
        'schedule': ['view', 'add'],
    },
    'teacher': {        'students': ['view'],
        'teachers': [],
        'classes': ['view'],
        'subjects': ['view'],
        'announcements': ['view'],
        'agenda': [],
        'leaves': ['add'],
        'levels': ['view', 'add'],
        'exams': ['view', 'add'],
        'messages': ['send'],
        'reports': [],
        'settings': [],
        'notes': ['view', 'add'],
        'nominations': ['view', 'add'],
        'survey': ['add'],
    },
    'student': {
        'students': [],
        'teachers': [],
        'classes': [],
        'subjects': [],
        'announcements': ['view'],
        'agenda': [],
        'leaves': [],
        'levels': [],
        'exams': [],
        'messages': [],
        'reports': [],
        'settings': [],
        'notes': ['view'],
        'survey': ['add'],
    },
}


class UserPermission(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='custom_permissions')
    permissions = models.JSONField('الصلاحيات', default=dict, blank=True)

    class Meta:
        verbose_name = 'صلاحية'
        verbose_name_plural = 'الصلاحيات'

    def get_permissions(self, module):
        return self.permissions.get(module, [])

    def has_perm(self, module, action):
        return action in self.permissions.get(module, [])

    def __str__(self):
        return f'{self.user.username} - صلاحيات'

    @staticmethod
    def get_defaults(role):
        return DEFAULT_PERMISSIONS.get(role, {})


class Class(models.Model):
    name = models.CharField('اسم الصف', max_length=100, unique=True)
    guardian = models.OneToOneField('Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='guardian_class', verbose_name='مربي الصف')

    class Meta:
        verbose_name = 'صف'
        verbose_name_plural = 'الصفوف'

    def __str__(self):
        return self.name


class Subject(models.Model):
    name = models.CharField('اسم المادة', max_length=100, unique=True)

    class Meta:
        verbose_name = 'مادة'
        verbose_name_plural = 'المواد'

    def __str__(self):
        return self.name


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    full_name = models.CharField('الاسم الكامل', max_length=200)
    email = models.EmailField('البريد الإلكتروني', blank=True)
    phone = models.CharField('رقم الهاتف', max_length=20, blank=True)
    id_number = models.CharField('رقم الهوية', max_length=50, blank=True, help_text='رقم هوية المعلم الوطني')
    hire_date = models.DateField('تاريخ التعيين', null=True, blank=True)
    birth_date = models.DateField('تاريخ الميلاد', null=True, blank=True)
    qualification = models.CharField('المؤهل العلمي', max_length=200, blank=True, help_text='مثال: بكالوريوس، ماجستير، دكتوراه')
    specialization = models.CharField('التخصص', max_length=200, blank=True, help_text='مثال: رياضيات، فيزياء، لغة عربية')
    classes = models.ManyToManyField(Class, verbose_name='الصفوف', blank=True, related_name='teachers')
    subjects = models.ManyToManyField(Subject, verbose_name='المواد', blank=True, related_name='teachers')
    created_at = models.DateTimeField('تاريخ الإضافة', auto_now_add=True)

    class Meta:
        verbose_name = 'معلم'
        verbose_name_plural = 'المعلمون'

    def __str__(self):
        return self.full_name


class TeacherNote(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='notes', verbose_name='المعلم')
    content = models.TextField('محتوى الملاحظة')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='كتب بواسطة')
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        verbose_name = 'ملاحظة معلم'
        verbose_name_plural = 'ملاحظات المعلمين'

    def __str__(self):
        return f'{self.teacher.full_name} - {self.created_at.strftime("%Y-%m-%d")}'


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField('رقم الهوية', max_length=20, unique=True)
    full_name = models.CharField('الاسم الكامل', max_length=200)
    student_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, verbose_name='الصف', related_name='students')
    parent_phone = models.CharField('هاتف ولي الأمر', max_length=20, blank=True)
    parent_name = models.CharField('اسم ولي الأمر', max_length=200, blank=True)
    address = models.TextField('العنوان', blank=True)
    birth_date = models.DateField('تاريخ الميلاد', null=True, blank=True)
    plain_password = models.CharField('كلمة المرور', max_length=100, blank=True, help_text='تظهر لمدير المدرسة فقط')
    created_at = models.DateTimeField('تاريخ التسجيل', auto_now_add=True)

    class Meta:
        verbose_name = 'طالب'
        verbose_name_plural = 'الطلاب'

    def __str__(self):
        return f'{self.full_name} - {self.student_class.name if self.student_class else "بدون صف"}'


class Note(models.Model):
    NOTE_TYPES = [
        ('تأخير', 'تأخير'),
        ('تأديبية', 'ملاحظة تأديبية'),
        ('سلوك', 'ملاحظة سلوك'),
        ('تحصيل', 'ملاحظة تحصيل'),
        ('أخرى', 'أخرى'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='notes', verbose_name='الطالب')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='كتب بواسطة')
    note_type = models.CharField('نوع الملاحظة', max_length=50, choices=NOTE_TYPES, default='أخرى')
    content = models.TextField('محتوى الملاحظة')
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    is_read = models.BooleanField('مقروءة', default=False)
    is_private = models.BooleanField('خاصة بالإدارة', default=False, help_text='إذا كانت خاصة، ستظهر فقط لمدير المدرسة')

    class Meta:
        verbose_name = 'ملاحظة طالب'
        verbose_name_plural = 'ملاحظات الطلاب'

    def __str__(self):
        return f'{self.student.full_name} - {self.note_type}'


class Announcement(models.Model):
    title = models.CharField('العنوان', max_length=200)
    content = models.TextField('المحتوى')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='الناشر')
    created_at = models.DateTimeField('تاريخ النشر', auto_now_add=True)
    is_active = models.BooleanField('نشط', default=True)

    class Meta:
        verbose_name = 'إعلان'
        verbose_name_plural = 'الإعلانات'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Agenda(models.Model):
    title = models.CharField('العنوان', max_length=200)
    description = models.TextField('الوصف', blank=True)
    due_date = models.DateField('تاريخ التنفيذ')
    is_completed = models.BooleanField('تم التنفيذ', default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='المنشئ')
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        verbose_name = 'أجندة'
        verbose_name_plural = 'الأجندات'
        ordering = ['due_date', 'created_at']

    def __str__(self):
        return self.title


class StudentLeave(models.Model):
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('approved', 'تمت الموافقة'),
        ('rejected', 'مرفوض'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='leaves', verbose_name='الطالب')
    leave_time = models.TimeField('وقت المغادرة')
    return_time = models.TimeField('وقت العودة', null=True, blank=True)
    reason = models.TextField('سبب المغادرة')
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='approved')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='موافق بواسطة')
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    leave_date = models.DateField('تاريخ المغادرة', auto_now_add=True)

    class Meta:
        verbose_name = 'إذن مغادرة'
        verbose_name_plural = 'أذونات المغادرة'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student.full_name} - {self.leave_time}'


class StudentAbsence(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='absences', verbose_name='الطالب')
    absence_date = models.DateField('تاريخ الغياب')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='سجل بواسطة')
    created_at = models.DateTimeField('تاريخ التسجيل', auto_now_add=True)

    class Meta:
        verbose_name = 'غياب طالب'
        verbose_name_plural = 'غياب الطلاب'
        ordering = ['-absence_date', 'student__full_name']
        constraints = [
            models.UniqueConstraint(fields=['student', 'absence_date'], name='unique_student_absence_day'),
        ]

    def __str__(self):
        return f'{self.student.full_name} - {self.absence_date}'


class StudentLevel(models.Model):
    LEVEL_CHOICES = [
        ('excellent', 'ممتاز'),
        ('very_good', 'جيد جداً'),
        ('good', 'جيد'),
        ('acceptable', 'مقبول'),
        ('weak', 'ضعيف'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='levels', verbose_name='الطالب')
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, verbose_name='المادة')
    level = models.CharField('المستوى', max_length=20, choices=LEVEL_CHOICES)
    notes = models.TextField('ملاحظات', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أضيف بواسطة')
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        verbose_name = 'مستوى طالب'
        verbose_name_plural = 'مستويات الطلاب'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student.full_name} - {self.get_level_display()}'


class ExamAnalysis(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, verbose_name='المادة')
    exam_name = models.CharField('اسم الامتحان', max_length=200)
    student_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, verbose_name='الصف')
    total_students = models.PositiveIntegerField('عدد الطلاب')
    passed_count = models.PositiveIntegerField('عدد الناجحين')
    failed_count = models.PositiveIntegerField('عدد الراسبين')
    pass_percentage = models.DecimalField('نسبة النجاح', max_digits=5, decimal_places=2, null=True, blank=True)
    fail_percentage = models.DecimalField('نسبة الرسوب', max_digits=5, decimal_places=2, null=True, blank=True)
    success_reasons = models.TextField('أسباب النجاح', blank=True)
    fail_reasons = models.TextField('أسباب الرسوب', blank=True)
    notes = models.TextField('ملاحظات إضافية', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أضيف بواسطة')
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        verbose_name = 'تحليل امتحان'
        verbose_name_plural = 'تحليلات الامتحانات'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.exam_name} - {self.subject.name if self.subject else "بدون مادة"}'


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_messages', verbose_name='المرسل')
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_messages', verbose_name='المستلم')
    subject = models.CharField('الموضوع', max_length=200)
    content = models.TextField('المحتوى')
    is_read = models.BooleanField('مقروء', default=False)
    parent_name = models.CharField('اسم ولي الأمر', max_length=200, blank=True, help_text='يستخدم عند إرسال ولي الأمر')
    parent_phone = models.CharField('هاتف ولي الأمر', max_length=20, blank=True)
    created_at = models.DateTimeField('تاريخ الإرسال', auto_now_add=True)

    class Meta:
        verbose_name = 'رسالة'
        verbose_name_plural = 'الرسائل'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.subject} - {self.sender.username if self.sender else self.parent_name or "مجهول"}'


class LessonLink(models.Model):
    title = models.CharField('العنوان', max_length=200)
    url = models.TextField('الرابط')
    lesson_datetime = models.DateTimeField('تاريخ ووقت الحصة', null=True, blank=True)
    is_active = models.BooleanField('نشط', default=True)
    created_at = models.DateTimeField('تاريخ الإضافة', auto_now_add=True)

    class Meta:
        verbose_name = 'رابط حصة'
        verbose_name_plural = 'روابط الحصص'
        ordering = ['lesson_datetime', 'created_at']

    def __str__(self):
        return self.title


class StudentLateness(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='lateness', verbose_name='الطالب')
    date = models.DateField('تاريخ التأخير', default=date.today)
    notes = models.TextField('ملاحظات', blank=True, help_text='سبب التأخير والإجراء المتبع')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='سجل بواسطة')
    created_at = models.DateTimeField('تاريخ التسجيل', auto_now_add=True)

    class Meta:
        verbose_name = 'تأخير طالب'
        verbose_name_plural = 'تأخيرات الطلاب'
        ordering = ['-date', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['student', 'date'], name='unique_lateness_per_day')
        ]

    def __str__(self):
        return f'{self.student.full_name} - {self.date}'


class SchoolInfo(models.Model):
    name_ar = models.CharField('اسم المدرسة (عربي)', max_length=200)
    name_en = models.CharField('اسم المدرسة (إنجليزي)', max_length=200)
    principal_name = models.CharField('اسم المدير', max_length=200)
    national_number = models.CharField('رقم المدرسة الوطني', max_length=50)
    latitude = models.FloatField('خط العرض', blank=True, null=True)
    longitude = models.FloatField('خط الطول', blank=True, null=True)
    school_logo = models.URLField('رابط شعار المدرسة', max_length=500, blank=True, null=True, default='', help_text='رابط مباشر للصورة (مثال: من Google Drive أو ImgBB)')
    ministry_logo = models.URLField('رابط شعار الوزارة', max_length=500, blank=True, null=True, default='', help_text='رابط مباشر للصورة')

    class Meta:
        verbose_name = 'بيانات المدرسة'
        verbose_name_plural = 'بيانات المدرسة'

    def __str__(self):
        return self.name_ar


class Meeting(models.Model):
    MEETING_TYPES = [('الجميع', 'الجميع'), ('زمري', 'زمري')]
    PLACES = [('غرفة المعلمين', 'غرفة المعلمين'), ('غرفة الإدارة', 'غرفة الإدارة')]

    meeting_type = models.CharField('نوع الاجتماع', max_length=50, choices=MEETING_TYPES)
    date = models.DateField('التاريخ')
    day = models.CharField('اليوم', max_length=50)
    time = models.TimeField('الساعة')
    place = models.CharField('مكان الاجتماع', max_length=100, choices=PLACES)
    goals = models.TextField('أهداف الاجتماع')
    minutes = models.TextField('محضر الاجتماع')
    meeting_number = models.CharField('رقم الاجتماع', max_length=20, unique=True)
    attendees = models.ManyToManyField('Teacher', verbose_name='المعلمون الحاضرون', blank=True)
    all_teachers = models.BooleanField('جميع المعلمين', default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'اجتماع'
        verbose_name_plural = 'الاجتماعات'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'اجتماع {self.meeting_type} - {self.date}'


class SupervisorVisit(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name='المعلم', related_name='supervisor_visits')
    visit_number = models.CharField('رقم الزيارة', max_length=50, blank=True)
    visit_date = models.DateField('تاريخ الزيارة')
    subject_area = models.CharField('المبحث', max_length=200, blank=True)
    lesson_topic = models.CharField('موضوع الدرس', max_length=300, blank=True)
    class_name = models.CharField('الصف', max_length=100, blank=True)
    section = models.CharField('الشعبة', max_length=50, blank=True)
    supervisor_name = models.CharField('اسم المشرف', max_length=200, blank=True)
    recommendations = models.TextField('توصيات المشرف', blank=True)
    admin_followup = models.TextField('متابعة الإدارة', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أدخل بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'زيارة مشرف'
        verbose_name_plural = 'زيارات المشرفين'
        ordering = ['-visit_date', '-created_at']

    def __str__(self):
        return f'زيارة {self.supervisor_name} - {self.teacher.full_name} - {self.visit_date}'


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name='المستخدم')
    title = models.CharField('العنوان', max_length=255)
    message = models.TextField('الرسالة', blank=True)
    link = models.CharField('الرابط', max_length=500, blank=True)
    is_read = models.BooleanField('مقروء', default=False)
    created_at = models.DateTimeField('تاريخ الإرسال', auto_now_add=True)

    class Meta:
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class VisitProgram(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name='المعلم', related_name='visit_program_entries')
    visit_date = models.DateField('تاريخ الحضور')
    lesson = models.CharField('الحصة', max_length=200, blank=True)
    notes = models.TextField('الملاحظات', blank=True, help_text='مثال: تم، لم يتم، أو أي ملاحظة أخرى')
    reminder_sent = models.BooleanField('تم إرسال التذكير', default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أدخل بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'برنامج زيارة'
        verbose_name_plural = 'برنامج الزيارات'
        ordering = ['-visit_date', 'teacher__full_name']

    def __str__(self):
        return f'{self.teacher.full_name} - {self.visit_date}'

    @property
    def day_name(self):
        days = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
        return days[self.visit_date.weekday()]

    @property
    def days_remaining(self):
        return (self.visit_date - date.today()).days

    @property
    def remaining_display(self):
        d = self.days_remaining
        if d > 0:
            return f'باقي {d} يوم'
        if d == 0:
            return 'اليوم'
        return f'مضى {-d} يوم'


class InspectionVisit(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name='المعلم', related_name='inspection_visits')
    visit_date = models.DateField('تاريخ الزيارة')
    visit_number = models.CharField('رقم الزيارة', max_length=50, blank=True)
    subject_area = models.CharField('المبحث', max_length=200, blank=True)
    lesson_topic = models.CharField('موضوع الدرس', max_length=300, blank=True)
    class_name = models.CharField('الصف', max_length=100, blank=True)
    section = models.CharField('الشعبة', max_length=50, blank=True)

    content_teaching = models.TextField('المحتوى التعليمي', blank=True)
    teaching_strategies = models.TextField('استراتيجيات التدريس', blank=True)
    evaluation_strategies = models.TextField('استراتيجيات التقويم', blank=True)
    other_matters = models.TextField('أمور أخرى', blank=True)
    plans_followup = models.TextField('متابعة الخطط وتنفيذها', blank=True)
    attendance_followup = models.TextField('متابعة الدوام المدرسي', blank=True)
    committees_followup = models.TextField('متابعة تفعيل اللجان المدرسية', blank=True)
    violence_policy = models.TextField('الالتزام بسياسة الحد من العنف', blank=True)
    recommendations = models.TextField('التوصيات للمعلم', blank=True)

    principal_sign_date = models.DateField('تاريخ توقيع المدير', blank=True, null=True)
    teacher_receipt_date = models.DateField('تاريخ استلام المعلم', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أدخل بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'زيارة إشرافية'
        verbose_name_plural = 'الزيارات الإشرافية'
        ordering = ['-visit_date', '-created_at']

    def __str__(self):
        return f'زيارة إشرافية - {self.teacher.full_name} - {self.visit_date}'


class Nomination(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, verbose_name='الطالب', related_name='nomination')
    student_class = models.ForeignKey(Class, on_delete=models.CASCADE, verbose_name='الصف', related_name='nominations')
    nominated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='رشّحه')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'ترشيح متفوق'
        verbose_name_plural = 'ترشيحات المتفوقين'
        ordering = ['student_class__name', 'student__full_name']

    def __str__(self):
        return f'{self.student.full_name} - {self.student_class.name}'


class Certificate(models.Model):
    nomination = models.OneToOneField(Nomination, on_delete=models.CASCADE, null=True, verbose_name='الترشيح', related_name='certificate')
    student_name = models.CharField('اسم الطالب', max_length=200, default='')
    class_name = models.CharField('الصف', max_length=100, default='')
    guardian_name = models.CharField('اسم مربي الصف', max_length=200, blank=True)
    principal_name = models.CharField('اسم مدير المدرسة', max_length=200, blank=True)
    cert_year = models.CharField('سنة التدريس', max_length=20, default='')
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أصدرها')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'شهادة تقدير'
        verbose_name_plural = 'شهادات التقدير'
        ordering = ['-created_at']

    def __str__(self):
        return f'شهادة {self.student_name} - {self.class_name}'


class TeacherScheduleEntry(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='schedule_entries', verbose_name='المعلم')
    day = models.CharField('اليوم', max_length=20)
    period = models.PositiveIntegerField('رقم الحصة')
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True, related_name='schedule_entries', verbose_name='المادة')
    student_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True, related_name='schedule_entries', verbose_name='الصف')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='عدل بواسطة')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'حصة في الجدول'
        verbose_name_plural = 'الجدول اليومي للمعلمين'
        ordering = ['day', 'period']
        constraints = [
            models.UniqueConstraint(fields=['teacher', 'day', 'period'], name='unique_teacher_schedule_cell'),
        ]

    def __str__(self):
        return f'{self.teacher.full_name} - {self.day} ح{self.period}'


class LoginCounter(models.Model):
    count = models.PositiveIntegerField('عدد مرات الدخول', default=0)
    last_reset = models.DateTimeField('آخر تصفير', null=True, blank=True)

    class Meta:
        verbose_name = 'عداد دخول الطلاب'
        verbose_name_plural = 'عداد دخول الطلاب'

    @classmethod
    def get(cls):
        return cls.objects.first() or cls.objects.create()

    @classmethod
    def increment(cls):
        obj = cls.get()
        obj.count += 1
        obj.save(update_fields=['count'])
        return obj.count

    @classmethod
    def reset(cls):
        obj = cls.get()
        obj.count = 0
        obj.last_reset = timezone.now()
        obj.save()

    def __str__(self):
        return f'عدد مرات الدخول: {self.count}'


class StudentSurvey(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='survey', verbose_name='الطالب')

    # ── المسح الصحي ──
    chronic_disease = models.BooleanField('مرض مزمن', default=False)
    chronic_disease_details = models.CharField('تفاصيل المرض المزمن', max_length=500, blank=True)
    regular_medication = models.BooleanField('أدوية منتظمة', default=False)
    medication_name = models.CharField('اسم الدواء', max_length=200, blank=True)
    has_allergy = models.BooleanField('حساسية', default=False)
    allergy_drugs = models.BooleanField('حساسية أدوية', default=False)
    allergy_food = models.BooleanField('حساسية أطعمة', default=False)
    allergy_dust = models.BooleanField('حساسية غبار', default=False)
    allergy_other = models.CharField('حساسية أخرى', max_length=300, blank=True)
    condition_asthma = models.BooleanField('الربو', default=False)
    condition_diabetes = models.BooleanField('السكري', default=False)
    condition_epilepsy = models.BooleanField('الصرع', default=False)
    condition_heart = models.BooleanField('مشاكل القلب', default=False)
    condition_hearing = models.BooleanField('ضعف السمع', default=False)
    condition_vision = models.BooleanField('ضعف البصر', default=False)
    condition_none = models.BooleanField('لا يوجد حالات صحية', default=False)
    needs_glasses = models.BooleanField('نظارات طبية', default=False)
    special_care = models.BooleanField('رعاية صحية خاصة', default=False)
    special_care_details = models.CharField('تفاصيل الرعاية الخاصة', max_length=500, blank=True)
    emergency_instructions = models.TextField('تعليمات خاصة للطبيب أو المدرسة', blank=True)

    # ── المسح الاجتماعي ──
    lives_with = models.CharField('يعيش مع', max_length=50, choices=[
        ('parents', 'الأب والأم'), ('father', 'الأب فقط'), ('mother', 'الأم فقط'),
        ('relative', 'أحد الأقارب'), ('other', 'أخرى'),
    ], default='parents')
    lives_with_other = models.CharField('محدد أخرى', max_length=200, blank=True)
    family_members_count = models.PositiveIntegerField('عدد أفراد الأسرة', null=True, blank=True)
    siblings_in_school_count = models.PositiveIntegerField('عدد الإخوة في المدرسة', null=True, blank=True)
    study_difficulties = models.BooleanField('صعوبات تؤثر على الدراسة', default=False)
    study_difficulties_details = models.CharField('تفاصيل الصعوبات', max_length=500, blank=True)
    support_academic = models.BooleanField('دعم أكاديمي', default=False)
    support_psychological = models.BooleanField('دعم نفسي', default=False)
    support_social = models.BooleanField('دعم اجتماعي', default=False)
    support_none = models.BooleanField('لا يحتاج دعم', default=False)
    has_study_place = models.BooleanField('مكان مخصص للمذاكرة', default=False)
    has_smartphone = models.BooleanField('هاتف ذكي', default=False)
    has_computer = models.BooleanField('جهاز حاسوب', default=False)
    has_internet = models.BooleanField('اتصال بالإنترنت', default=False)
    has_no_device = models.BooleanField('لا يتوفر أي منها', default=False)
    participates_activities = models.BooleanField('أنشطة رياضية/ثقافية خارج المدرسة', default=False)
    family_special_conditions = models.BooleanField('ظروف خاصة للأسرة', default=False)
    family_special_conditions_details = models.CharField('تفاصيل الظروف الخاصة', max_length=500, blank=True)
    contact_counselor = models.BooleanField('التواصل مع المرشد التربوي', default=False)
    contact_method = models.CharField('أفضل وسيلة تواصل', max_length=20, choices=[('phone', 'اتصال هاتفي'), ('whatsapp', 'واتساب'), ('sms', 'رسالة نصية')], default='', blank=True)

    # ── أسئلة اختيارية ──
    strengths = models.TextField('أبرز نقاط القوة', blank=True)
    difficulties_notes = models.TextField('أبرز الصعوبات', blank=True)
    subjects_need_support = models.TextField('المواد التي يحتاج دعم', blank=True)
    suggestions = models.TextField('اقتراحات لخدمة الطالب', blank=True)

    submitted_at = models.DateTimeField('تاريخ التعبئة', auto_now_add=True)
    updated_at = models.DateTimeField('آخر تعديل', auto_now=True)

    class Meta:
        verbose_name = 'مسح صحي واجتماعي'
        verbose_name_plural = 'المسح الصحي والاجتماعي'
        ordering = ['student__full_name']

    def __str__(self):
        return f'مسح {self.student.full_name}'


class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions', verbose_name='المستخدم')
    endpoint = models.TextField('نقطة الاشتراك', unique=True)
    p256dh = models.TextField('مفتاح p256dh')
    auth = models.TextField('مفتاح auth')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'اشتراك إشعارات'
        verbose_name_plural = 'اشتراكات الإشعارات'

    def __str__(self):
        return f'اشتراك {self.user.username}'
