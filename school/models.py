from django.db import models
from django.contrib.auth.models import User


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
        'settings': ['whatsapp', 'accounts'],
        'notes': ['view', 'add'],
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
    },
    'secretary': {
        'students': ['view', 'add', 'edit', 'import', 'export'],
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
    },
    'teacher': {
        'students': ['view'],
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
    hire_date = models.DateField('تاريخ التعيين', null=True, blank=True)
    birth_date = models.DateField('تاريخ الميلاد', null=True, blank=True)
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
    url = models.URLField('الرابط', max_length=500)
    lesson_datetime = models.DateTimeField('تاريخ ووقت الحصة', null=True, blank=True)
    is_active = models.BooleanField('نشط', default=True)
    created_at = models.DateTimeField('تاريخ الإضافة', auto_now_add=True)

    class Meta:
        verbose_name = 'رابط حصة'
        verbose_name_plural = 'روابط الحصص'
        ordering = ['lesson_datetime', 'created_at']

    def __str__(self):
        return self.title
