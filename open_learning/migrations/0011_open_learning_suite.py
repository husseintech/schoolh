from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('open_learning', '0010_studentlessonprogress'),
        ('school', '0040_noobjection_extra_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='LessonActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان النشاط')),
                ('instructions', models.TextField(verbose_name='تعليمات النشاط')),
                ('activity_type', models.CharField(choices=[('practice', 'تدريب'), ('discussion', 'مناقشة'), ('exploration', 'استكشاف'), ('project', 'مشروع قصير')], default='practice', max_length=20, verbose_name='نوع النشاط')),
                ('is_required', models.BooleanField(default=False, verbose_name='إلزامي')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='الترتيب')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='learning_activities', to='open_learning.learninglesson', verbose_name='الدرس')),
            ],
            options={'verbose_name': 'نشاط درس', 'verbose_name_plural': 'أنشطة الدروس', 'ordering': ['order', 'id']},
        ),
        migrations.CreateModel(
            name='LessonQuiz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان الاختبار')),
                ('instructions', models.TextField(blank=True, verbose_name='التعليمات')),
                ('is_published', models.BooleanField(default=False, verbose_name='منشور للطلاب')),
                ('passing_score', models.PositiveSmallIntegerField(default=50, verbose_name='نسبة النجاح')),
                ('max_attempts', models.PositiveSmallIntegerField(default=2, verbose_name='عدد المحاولات')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='learning_quizzes', to='open_learning.learninglesson', verbose_name='الدرس')),
            ],
            options={'verbose_name': 'اختبار درس', 'verbose_name_plural': 'اختبارات الدروس', 'ordering': ['id']},
        ),
        migrations.CreateModel(
            name='LessonAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان الواجب')),
                ('instructions', models.TextField(verbose_name='التعليمات')),
                ('due_at', models.DateTimeField(blank=True, null=True, verbose_name='موعد التسليم')),
                ('points', models.PositiveSmallIntegerField(default=10, verbose_name='العلامة')),
                ('is_published', models.BooleanField(default=False, verbose_name='منشور للطلاب')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='learning_assignments', to='open_learning.learninglesson', verbose_name='الدرس')),
            ],
            options={'verbose_name': 'واجب درس', 'verbose_name_plural': 'واجبات الدروس', 'ordering': ['id']},
        ),
        migrations.CreateModel(
            name='OpenResourceMetadata',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('license_type', models.CharField(choices=[('cc0', 'CC0'), ('cc_by', 'CC BY'), ('cc_by_sa', 'CC BY-SA'), ('cc_by_nc', 'CC BY-NC'), ('public_domain', 'ملكية عامة'), ('unknown', 'غير محدد')], default='unknown', max_length=20, verbose_name='الترخيص')),
                ('author', models.CharField(blank=True, max_length=250, verbose_name='المؤلف/الجهة')),
                ('attribution', models.TextField(blank=True, verbose_name='صيغة النسبة للمصدر')),
                ('source_url', models.URLField(blank=True, max_length=700, verbose_name='رابط المصدر الأصلي')),
                ('verified_open_license', models.BooleanField(default=False, verbose_name='تم التحقق من الترخيص المفتوح')),
                ('verified_at', models.DateTimeField(blank=True, null=True, verbose_name='تاريخ التحقق')),
                ('library', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='open_metadata', to='open_learning.learningresourcelibrary', verbose_name='المصدر')),
            ],
            options={'verbose_name': 'بيانات ترخيص مصدر مفتوح', 'verbose_name_plural': 'بيانات تراخيص المصادر المفتوحة'},
        ),
        migrations.CreateModel(
            name='QuizQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(verbose_name='السؤال')),
                ('question_type', models.CharField(choices=[('mcq', 'اختيار من متعدد'), ('true_false', 'صح/خطأ')], default='mcq', max_length=20, verbose_name='نوع السؤال')),
                ('options', models.JSONField(blank=True, default=list, verbose_name='الخيارات')),
                ('correct_answer', models.CharField(max_length=300, verbose_name='الإجابة الصحيحة')),
                ('points', models.PositiveSmallIntegerField(default=1, verbose_name='العلامة')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='الترتيب')),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='open_learning.lessonquiz', verbose_name='الاختبار')),
            ],
            options={'verbose_name': 'سؤال اختبار', 'verbose_name_plural': 'أسئلة الاختبارات', 'ordering': ['order', 'id']},
        ),
        migrations.CreateModel(
            name='QuizAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.DecimalField(decimal_places=2, default=0, max_digits=7, verbose_name='العلامة')),
                ('max_score', models.DecimalField(decimal_places=2, default=0, max_digits=7, verbose_name='العلامة الكاملة')),
                ('percentage', models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='النسبة')),
                ('passed', models.BooleanField(default=False, verbose_name='ناجح')),
                ('submitted_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسليم')),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='open_learning.lessonquiz', verbose_name='الاختبار')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='open_learning_quiz_attempts', to='school.student', verbose_name='الطالب')),
            ],
            options={'verbose_name': 'محاولة اختبار', 'verbose_name_plural': 'محاولات الاختبارات', 'ordering': ['-submitted_at']},
        ),
        migrations.CreateModel(
            name='StudentActivityCompletion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('completed_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإكمال')),
                ('activity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='completions', to='open_learning.lessonactivity', verbose_name='النشاط')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='open_learning_activity_completions', to='school.student', verbose_name='الطالب')),
            ],
            options={'verbose_name': 'إكمال نشاط', 'verbose_name_plural': 'إكمال الأنشطة'},
        ),
        migrations.CreateModel(
            name='AssignmentSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answer_text', models.TextField(blank=True, verbose_name='الإجابة')),
                ('answer_link', models.URLField(blank=True, max_length=600, verbose_name='رابط إضافي')),
                ('submitted_at', models.DateTimeField(auto_now=True, verbose_name='تاريخ التسليم')),
                ('status', models.CharField(choices=[('submitted', 'تم التسليم'), ('reviewed', 'تمت المراجعة')], default='submitted', max_length=20, verbose_name='الحالة')),
                ('grade', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name='العلامة')),
                ('feedback', models.TextField(blank=True, verbose_name='ملاحظة المعلم')),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='open_learning.lessonassignment', verbose_name='الواجب')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='open_learning_assignment_submissions', to='school.student', verbose_name='الطالب')),
            ],
            options={'verbose_name': 'تسليم واجب', 'verbose_name_plural': 'تسليمات الواجبات', 'ordering': ['-submitted_at']},
        ),
        migrations.CreateModel(
            name='QuizAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answer', models.CharField(blank=True, max_length=500, verbose_name='الإجابة')),
                ('is_correct', models.BooleanField(default=False, verbose_name='صحيحة')),
                ('awarded_points', models.DecimalField(decimal_places=2, default=0, max_digits=6, verbose_name='العلامة المحتسبة')),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='open_learning.quizattempt', verbose_name='المحاولة')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='open_learning.quizquestion', verbose_name='السؤال')),
            ],
            options={'verbose_name': 'إجابة اختبار', 'verbose_name_plural': 'إجابات الاختبارات'},
        ),
        migrations.AddConstraint(model_name='studentactivitycompletion', constraint=models.UniqueConstraint(fields=('student', 'activity'), name='unique_student_activity_completion')),
        migrations.AddConstraint(model_name='assignmentsubmission', constraint=models.UniqueConstraint(fields=('student', 'assignment'), name='unique_student_assignment_submission')),
        migrations.AddConstraint(model_name='quizanswer', constraint=models.UniqueConstraint(fields=('attempt', 'question'), name='unique_attempt_question_answer')),
    ]
