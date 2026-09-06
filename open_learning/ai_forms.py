from django import forms


class SelectedSourceForm(forms.Form):
    title = forms.CharField(label='عنوان المادة المختارة', max_length=200,
                           widget=forms.TextInput(attrs={'class': 'form-control'}))
    url = forms.URLField(label='رابط المادة نفسها', max_length=2000,
                         widget=forms.URLInput(attrs={'class': 'form-control', 'dir': 'ltr', 'placeholder': 'https://…'}))
    resource_type = forms.ChoiceField(label='نوع المصدر', choices=[('video', 'فيديو'), ('reading', 'قراءة / ورقة عمل'),
        ('image', 'صورة'), ('simulation', 'محاكاة'), ('activity', 'نشاط'), ('link', 'رابط')],
        widget=forms.Select(attrs={'class': 'form-select'}))

    def clean_url(self):
        from .services.ai_service import normalize_url
        url = self.cleaned_data['url']
        if not normalize_url(url):
            raise forms.ValidationError('أدخل رابط http أو https صالحًا دون معلومات تسجيل دخول.')
        return url


class LessonBriefForm(forms.Form):
    grade = forms.IntegerField(label='الصف الدراسي المستهدف', min_value=1, max_value=12,
                               widget=forms.NumberInput(attrs={'class': 'form-control'}))
    focus = forms.CharField(label='ما المفهوم الذي تريد تدريسه تحديدًا؟', min_length=20, max_length=2000,
                            help_text='مثال: تمييز الفاعل في جملة فعلية بسيطة وضبطه بالضمة، دون المثنى والجمع.',
                            widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    prior_knowledge = forms.CharField(label='ما الذي يعرفه الطلاب مسبقًا؟', required=False, max_length=1000,
                                      widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
    reference_text = forms.CharField(label='مقتطف من الدرس أو نقاط الكتاب الأساسية (اختياري)',
                                     required=False, max_length=6000,
                                     help_text='يساعد على مطابقة المحتوى للمنهاج. لا تُدخل بيانات شخصية للطلاب.',
                                     widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}))
    duration = forms.IntegerField(label='مدة الحصة بالدقائق', min_value=15, max_value=120, initial=40,
                                  widget=forms.NumberInput(attrs={'class': 'form-control'}))
    learner_level = forms.ChoiceField(label='مستوى الطلاب في هذا المفهوم',
                                      choices=[('mixed', 'متفاوت'), ('beginner', 'مبتدئ'), ('advanced', 'متقدم')],
                                      widget=forms.Select(attrs={'class': 'form-select'}))
