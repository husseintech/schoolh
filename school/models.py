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


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField('رقم الهوية', max_length=20, unique=True)
    full_name = models.CharField('الاسم الكامل', max_length=200)
    class_name = models.CharField('الصف', max_length=100)
    parent_phone = models.CharField('هاتف ولي الأمر', max_length=20, blank=True)
    created_at = models.DateTimeField('تاريخ التسجيل', auto_now_add=True)

    def __str__(self):
        return f'{self.full_name} - {self.class_name}'


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

    def __str__(self):
        return f'{self.student.full_name} - {self.note_type}'
