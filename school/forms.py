from django import forms
from django.contrib.auth.models import User
from .models import Student, Note


class StudentForm(forms.ModelForm):
    password = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput, required=True)
    username = forms.CharField(label='اسم المستخدم', required=True)

    class Meta:
        model = Student
        fields = ['username', 'password', 'student_id', 'full_name', 'class_name', 'parent_phone']

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


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['student', 'note_type', 'content']
        labels = {
            'student': 'الطالب',
            'note_type': 'نوع الملاحظة',
            'content': 'نص الملاحظة',
        }


class StudentEditForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['student_id', 'full_name', 'class_name', 'parent_phone']
        labels = {
            'student_id': 'رقم الهوية',
            'full_name': 'الاسم الكامل',
            'class_name': 'الصف',
            'parent_phone': 'هاتف ولي الأمر',
        }
