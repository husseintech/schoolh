from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'مدير'),
        ('teacher', 'معلم'),
        ('student', 'طالب'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField('الدور', max_length=20, choices=ROLE_CHOICES, default='student')
    phone = models.CharField('رقم الهاتف', max_length=20, blank=True)

    def __str__(self):
        return f'{self.user.username} - {self.get_role_display()}'


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
