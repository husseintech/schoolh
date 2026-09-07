from django import forms

from school.models import Student

from .models import SchoolRadioEntry


class SchoolRadioEntryForm(forms.ModelForm):
    class Meta:
        model = SchoolRadioEntry
        fields = [
            'event_date', 'title', 'topic', 'category', 'presenters', 'participants',
            'additional_presenters', 'additional_participants', 'notes',
        ]
        widgets = {
            'event_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: إذاعة يوم الأسير الفلسطيني'}),
            'topic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'الموضوع الذي ستتناوله الإذاعة'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'presenters': forms.SelectMultiple(attrs={'class': 'form-select select2'}),
            'participants': forms.SelectMultiple(attrs={'class': 'form-select select2'}),
            'additional_presenters': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2, 'placeholder': 'أسماء غير موجودة في قائمة الطلاب، كل اسم في سطر'
            }),
            'additional_participants': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2, 'placeholder': 'أسماء إضافية، كل اسم في سطر'
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        students = Student.objects.select_related('student_class').order_by('student_class__name', 'full_name')
        self.fields['presenters'].queryset = students
        self.fields['participants'].queryset = students
        self.fields['presenters'].required = False
        self.fields['participants'].required = False
        self.fields['presenters'].label_from_instance = self._student_label
        self.fields['participants'].label_from_instance = self._student_label

    @staticmethod
    def _student_label(student):
        class_name = student.student_class.name if student.student_class else 'بدون صف'
        return f'{student.full_name} — {class_name}'
