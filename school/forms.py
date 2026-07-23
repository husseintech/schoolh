from django import forms
from django.contrib.auth.models import User
from .models import Profile, Student, Note, Teacher, TeacherNote, Announcement, Agenda, StudentLeave, StudentLevel, ExamAnalysis, Message, Class, Subject


class StudentForm(forms.ModelForm):
    password = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput, required=True)
    username = forms.CharField(label='اسم المستخدم', required=True)

    class Meta:
        model = Student
        fields = ['username', 'password', 'student_id', 'full_name', 'student_class', 'parent_phone', 'parent_name', 'address', 'birth_date']
        labels = {
            'student_id': 'رقم الهوية',
            'full_name': 'الاسم الكامل',
            'student_class': 'الصف',
            'parent_phone': 'هاتف ولي الأمر',
            'parent_name': 'اسم ولي الأمر',
            'address': 'العنوان',
            'birth_date': 'تاريخ الميلاد',
        }
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def save(self, commit=True):
        student = super().save(commit=False)
        username = self.cleaned_data['username']
        password = self.cleaned_data['password']
        if commit:
            user = User.objects.create_user(username=username, password=password)
            Profile.objects.create(user=user, role='student')
            student.user = user
            student.save()
        return student


class StudentEditForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['student_id', 'full_name', 'student_class', 'parent_phone', 'parent_name', 'address', 'birth_date']
        labels = {
            'student_id': 'رقم الهوية',
            'full_name': 'الاسم الكامل',
            'student_class': 'الصف',
            'parent_phone': 'هاتف ولي الأمر',
            'parent_name': 'اسم ولي الأمر',
            'address': 'العنوان',
            'birth_date': 'تاريخ الميلاد',
        }
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['student', 'note_type', 'content', 'is_private']
        labels = {
            'student': 'الطالب',
            'note_type': 'نوع الملاحظة',
            'content': 'نص الملاحظة',
            'is_private': 'خاصة بالإدارة فقط',
        }
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
        }


class TeacherForm(forms.ModelForm):
    password = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput, required=True)
    username = forms.CharField(label='اسم المستخدم', required=True)

    class Meta:
        model = Teacher
        fields = ['username', 'password', 'full_name', 'email', 'phone', 'hire_date', 'birth_date', 'classes', 'subjects']
        labels = {
            'full_name': 'الاسم الكامل',
            'email': 'البريد الإلكتروني',
            'phone': 'رقم الهاتف',
            'hire_date': 'تاريخ التعيين',
            'birth_date': 'تاريخ الميلاد',
            'classes': 'الصفوف التي يدرسها',
            'subjects': 'المواد',
        }
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'classes': forms.SelectMultiple(attrs={'class': 'select2'}),
            'subjects': forms.SelectMultiple(attrs={'class': 'select2'}),
        }

    def save(self, commit=True):
        teacher = super().save(commit=False)
        username = self.cleaned_data['username']
        password = self.cleaned_data['password']
        if commit:
            user = User.objects.create_user(username=username, password=password)
            Profile.objects.create(user=user, role='teacher')
            teacher.user = user
            teacher.save()
            self.save_m2m()
        return teacher


class TeacherEditForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ['full_name', 'email', 'phone', 'hire_date', 'birth_date', 'classes', 'subjects']
        labels = {
            'full_name': 'الاسم الكامل',
            'email': 'البريد الإلكتروني',
            'phone': 'رقم الهاتف',
            'hire_date': 'تاريخ التعيين',
            'birth_date': 'تاريخ الميلاد',
            'classes': 'الصفوف التي يدرسها',
            'subjects': 'المواد',
        }
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'classes': forms.SelectMultiple(attrs={'class': 'select2'}),
            'subjects': forms.SelectMultiple(attrs={'class': 'select2'}),
        }


class TeacherNoteForm(forms.ModelForm):
    class Meta:
        model = TeacherNote
        fields = ['teacher', 'content']
        labels = {
            'teacher': 'المعلم',
            'content': 'الملاحظة',
        }
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
        }


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'is_active']
        labels = {
            'title': 'العنوان',
            'content': 'المحتوى',
            'is_active': 'نشط (ظاهر للجميع)',
        }
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5}),
        }


class AgendaForm(forms.ModelForm):
    class Meta:
        model = Agenda
        fields = ['title', 'description', 'due_date']
        labels = {
            'title': 'العنوان',
            'description': 'الوصف',
            'due_date': 'تاريخ التنفيذ',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }


class AgendaCompleteForm(forms.ModelForm):
    class Meta:
        model = Agenda
        fields = ['is_completed']


class StudentLeaveForm(forms.ModelForm):
    class Meta:
        model = StudentLeave
        fields = ['student', 'leave_time', 'return_time', 'reason']
        labels = {
            'student': 'الطالب',
            'leave_time': 'وقت المغادرة',
            'return_time': 'وقت العودة',
            'reason': 'السبب',
        }
        widgets = {
            'leave_time': forms.TimeInput(attrs={'type': 'time'}),
            'return_time': forms.TimeInput(attrs={'type': 'time'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }


class StudentLevelForm(forms.ModelForm):
    class Meta:
        model = StudentLevel
        fields = ['student', 'subject', 'level', 'notes']
        labels = {
            'student': 'الطالب',
            'subject': 'المادة',
            'level': 'المستوى',
            'notes': 'ملاحظات',
        }
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class ExamAnalysisForm(forms.ModelForm):
    class Meta:
        model = ExamAnalysis
        fields = ['subject', 'exam_name', 'student_class', 'total_students', 'passed_count', 'failed_count', 'success_reasons', 'fail_reasons', 'notes']
        labels = {
            'subject': 'المادة',
            'exam_name': 'اسم الامتحان',
            'student_class': 'الصف',
            'total_students': 'عدد الطلاب',
            'passed_count': 'عدد الناجحين',
            'failed_count': 'عدد الراسبين',
            'success_reasons': 'أسباب النجاح',
            'fail_reasons': 'أسباب الرسوب',
            'notes': 'ملاحظات إضافية',
        }
        widgets = {
            'success_reasons': forms.Textarea(attrs={'rows': 3}),
            'fail_reasons': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['recipient', 'subject', 'content']
        labels = {
            'recipient': 'المستلم',
            'subject': 'الموضوع',
            'content': 'الرسالة',
        }
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5}),
        }


class ParentMessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['parent_name', 'parent_phone', 'subject', 'content']
        labels = {
            'parent_name': 'اسمك',
            'parent_phone': 'رقم هاتفك',
            'subject': 'الموضوع',
            'content': 'الرسالة',
        }
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5}),
        }


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name']
        labels = {
            'name': 'اسم الصف',
        }


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name']
        labels = {
            'name': 'اسم المادة',
        }
