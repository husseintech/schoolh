from django import forms
from django.contrib.auth.models import User
from .models import Profile, Student, Note, Teacher, TeacherNote, Announcement, Agenda, StudentLeave, StudentLevel, ExamAnalysis, Message, Class, Subject, StudentSurvey


class StudentForm(forms.ModelForm):
    password = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput, required=False, help_text='اترك فارغة لإنشاء كلمة مرور تلقائية من رقم الهوية')
    username = forms.CharField(label='اسم المستخدم', required=False, help_text='اترك فارغة لاستخدام رقم الهوية كاسم مستخدم')

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
        username = self.cleaned_data.get('username', '').strip() or student.student_id
        password = self.cleaned_data.get('password')
        if not password:
            password = student.student_id[-6:] if len(student.student_id) >= 6 else student.student_id
        if commit:
            user = User.objects.create_user(username=username, password=password)
            Profile.objects.create(user=user, role='student')
            student.user = user
            student.plain_password = password
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
    password = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput, required=False,
                               help_text='اتركها فارغة لاستخدام آخر 6 أرقام من رقم الهوية')
    username = forms.CharField(label='اسم المستخدم', required=False,
                               help_text='اتركه فارغاً لاستخدام رقم الهوية كاسم مستخدم')

    class Meta:
        model = Teacher
        fields = ['username', 'password', 'full_name', 'id_number', 'email', 'phone', 'hire_date', 'birth_date', 'qualification', 'specialization', 'classes', 'subjects']
        labels = {
            'full_name': 'الاسم الكامل',
            'id_number': 'رقم الهوية',
            'email': 'البريد الإلكتروني',
            'phone': 'رقم الهاتف',
            'hire_date': 'تاريخ التعيين',
            'birth_date': 'تاريخ الميلاد',
            'qualification': 'المؤهل العلمي',
            'specialization': 'التخصص',
            'classes': 'الصفوف التي يدرسها',
            'subjects': 'المواد',
        }
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'qualification': forms.Select(choices=[('', 'اختر...'), ('دبلوم', 'دبلوم'), ('بكالوريوس', 'بكالوريوس'), ('ماجستير', 'ماجستير'), ('دكتوراه', 'دكتوراه')]),
            'classes': forms.SelectMultiple(attrs={'class': 'select2'}),
            'subjects': forms.SelectMultiple(attrs={'class': 'select2'}),
        }

    def clean(self):
        cleaned = super().clean()
        id_number = str(cleaned.get('id_number', '') or '').strip()
        username = str(cleaned.get('username', '') or '').strip()
        if not username:
            username = id_number
        if not username:
            self.add_error('username', 'أدخل اسم المستخدم أو رقم الهوية')
            return cleaned
        if User.objects.filter(username=username).exists():
            self.add_error('username', f'اسم المستخدم {username} مستخدم مسبقاً')
        cleaned['username'] = username
        return cleaned

    def save(self, commit=True):
        teacher = super().save(commit=False)
        username = self.cleaned_data['username']
        password = self.cleaned_data.get('password', '') or (username[-6:] if len(username) >= 6 else username)
        if commit:
            user = User.objects.create_user(username=username, password=password)
            Profile.objects.create(user=user, role='teacher')
            teacher.user = user
            teacher.save()
            self.save_m2m()
        return teacher


class TeacherEditForm(forms.ModelForm):
    username = forms.CharField(label='اسم المستخدم', required=False, disabled=True,
                               help_text='لا يمكن تعديل اسم المستخدم')
    password = forms.CharField(label='كلمة المرور الجديدة', widget=forms.PasswordInput,
                               required=False, help_text='اتركه فارغاً إذا لم ترد التغيير')

    class Meta:
        model = Teacher
        fields = ['username', 'password', 'full_name', 'email', 'phone', 'id_number', 'hire_date', 'birth_date', 'qualification', 'specialization', 'classes', 'subjects']
        labels = {
            'full_name': 'الاسم الكامل',
            'email': 'البريد الإلكتروني',
            'phone': 'رقم الهاتف',
            'id_number': 'رقم الهوية',
            'hire_date': 'تاريخ التعيين',
            'birth_date': 'تاريخ الميلاد',
            'qualification': 'المؤهل العلمي',
            'specialization': 'التخصص',
            'classes': 'الصفوف التي يدرسها',
            'subjects': 'المواد',
        }
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'qualification': forms.Select(choices=[('', 'اختر...'), ('دبلوم', 'دبلوم'), ('بكالوريوس', 'بكالوريوس'), ('ماجستير', 'ماجستير'), ('دكتوراه', 'دكتوراه')]),
            'classes': forms.SelectMultiple(attrs={'class': 'select2'}),
            'subjects': forms.SelectMultiple(attrs={'class': 'select2'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields['username'].initial = self.instance.user.username


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'leave_time' not in self.data:
            from datetime import datetime
            self.initial['leave_time'] = datetime.now().strftime('%H:%M')


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


class StudentSurveyForm(forms.ModelForm):
    class Meta:
        model = StudentSurvey
        fields = [
            # health
            'chronic_disease', 'chronic_disease_details',
            'regular_medication', 'medication_name',
            'has_allergy', 'allergy_drugs', 'allergy_food', 'allergy_dust', 'allergy_other',
            'condition_asthma', 'condition_diabetes', 'condition_epilepsy', 'condition_heart',
            'condition_hearing', 'condition_vision', 'condition_none',
            'needs_glasses',
            'special_care', 'special_care_details',
            'emergency_instructions',
            # social
            'lives_with', 'lives_with_other',
            'family_members_count', 'siblings_in_school_count',
            'study_difficulties', 'study_difficulties_details',
            'support_academic', 'support_psychological', 'support_social', 'support_none',
            'has_study_place',
            'has_smartphone', 'has_computer', 'has_internet', 'has_no_device',
            'participates_activities',
            'family_special_conditions', 'family_special_conditions_details',
            'contact_counselor', 'contact_method',
            # optional
            'strengths', 'difficulties_notes', 'subjects_need_support', 'suggestions',
        ]
        widgets = {
            'chronic_disease': forms.CheckboxInput(attrs={'class': 'form-check-input survey-radio', 'data-target': 'chronic_disease_details'}),
            'chronic_disease_details': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'يرجى التوضيح', 'hidden': True}),
            'regular_medication': forms.CheckboxInput(attrs={'class': 'form-check-input survey-radio', 'data-target': 'medication_name'}),
            'medication_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اذكر اسم الدواء', 'hidden': True}),
            'has_allergy': forms.CheckboxInput(attrs={'class': 'form-check-input survey-radio'}),
            'allergy_drugs': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'allergy_food': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'allergy_dust': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'allergy_other': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'أخرى: اذكرها'}),
            'condition_asthma': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'condition_diabetes': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'condition_epilepsy': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'condition_heart': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'condition_hearing': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'condition_vision': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'condition_none': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check survey-no'}),
            'needs_glasses': forms.CheckboxInput(attrs={'class': 'form-check-input survey-radio'}),
            'special_care': forms.CheckboxInput(attrs={'class': 'form-check-input survey-radio', 'data-target': 'special_care_details'}),
            'special_care_details': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'يرجى التوضيح', 'hidden': True}),
            'emergency_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'أي تعليمات خاصة للطبيب أو المدرسة في حال الطوارئ'}),
            'lives_with': forms.RadioSelect(attrs={'class': 'survey-radio'}),
            'lives_with_other': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اذكر من يعيش معه'}),
            'family_members_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'siblings_in_school_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'study_difficulties': forms.CheckboxInput(attrs={'class': 'form-check-input survey-radio', 'data-target': 'study_difficulties_details'}),
            'study_difficulties_details': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'يرجى التوضيح', 'hidden': True}),
            'support_academic': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'support_psychological': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'support_social': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'support_none': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check survey-no'}),
            'has_study_place': forms.CheckboxInput(attrs={'class': 'form-check-input survey-radio'}),
            'has_smartphone': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'has_computer': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'has_internet': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check'}),
            'has_no_device': forms.CheckboxInput(attrs={'class': 'form-check-input survey-check survey-no'}),
            'participates_activities': forms.CheckboxInput(attrs={'class': 'form-check-input survey-radio'}),
            'family_special_conditions': forms.CheckboxInput(attrs={'class': 'form-check-input survey-radio', 'data-target': 'family_special_conditions_details'}),
            'family_special_conditions_details': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نعم (اختياري)', 'hidden': True}),
            'contact_counselor': forms.CheckboxInput(attrs={'class': 'form-check-input survey-radio'}),
            'contact_method': forms.RadioSelect(attrs={'class': 'survey-radio'}),
            'strengths': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'difficulties_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'subjects_need_support': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'suggestions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'chronic_disease': 'نعم، يرجى التوضيح',
            'regular_medication': 'نعم، اذكر اسم الدواء',
            'has_allergy': 'نعم، الطالب لديه حساسية',
            'needs_glasses': 'نعم، يحتاج نظارات',
            'special_care': 'نعم، يحتاج رعاية صحية خاصة',
            'study_difficulties': 'نعم، يعاني صعوبات',
            'has_study_place': 'نعم',
            'participates_activities': 'نعم',
            'family_special_conditions': 'نعم',
            'contact_counselor': 'نعم',
            'lives_with': 'يعيش الطالب مع',
            'contact_method': 'أفضل وسيلة للتواصل مع ولي الأمر',
        }
