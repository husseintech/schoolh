from django import forms


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
