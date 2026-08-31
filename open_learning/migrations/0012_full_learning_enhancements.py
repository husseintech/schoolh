from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('school', '0040_noobjection_extra_fields'),
        ('open_learning', '0011_open_learning_suite'),
    ]

    operations = [
        migrations.CreateModel(
            name='GuardianStudentLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('relation', models.CharField(default='ولي أمر', max_length=50, verbose_name='صلة القرابة')),
                ('is_active', models.BooleanField(default=True, verbose_name='نشط')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الربط')),
                ('guardian', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='open_learning_guardian_links', to=settings.AUTH_USER_MODEL, verbose_name='ولي الأمر')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='open_learning_guardian_links', to='school.student', verbose_name='الطالب')),
            ],
            options={
                'verbose_name': 'ربط ولي أمر بطالب',
                'verbose_name_plural': 'روابط أولياء الأمور بالطلاب',
            },
        ),
        migrations.CreateModel(
            name='LearningAchievement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('lesson_complete', 'إكمال درس'), ('perfect_quiz', 'علامة كاملة في اختبار'), ('consistent', 'مواظبة تعليمية')], max_length=30, verbose_name='نوع الإنجاز')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان الإنجاز')),
                ('description', models.CharField(blank=True, max_length=500, verbose_name='الوصف')),
                ('awarded_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنجاز')),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='achievements', to='open_learning.learninglesson', verbose_name='الدرس')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='open_learning_achievements', to='school.student', verbose_name='الطالب')),
            ],
            options={
                'verbose_name': 'إنجاز تعلم',
                'verbose_name_plural': 'إنجازات التعلم',
                'ordering': ['-awarded_at'],
            },
        ),
        migrations.CreateModel(
            name='LearningResourceFavorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة للمفضلة')),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to='open_learning.learningresourcelibrary', verbose_name='المصدر')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='open_learning_resource_favorites', to='school.student', verbose_name='الطالب')),
            ],
            options={
                'verbose_name': 'مصدر مفضل',
                'verbose_name_plural': 'المصادر المفضلة',
            },
        ),
        migrations.CreateModel(
            name='LearningResourceRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name='التقييم')),
                ('note', models.CharField(blank=True, max_length=300, verbose_name='ملاحظة')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ratings', to='open_learning.learningresourcelibrary', verbose_name='المصدر')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='open_learning_resource_ratings', to='school.student', verbose_name='الطالب')),
            ],
            options={
                'verbose_name': 'تقييم مصدر',
                'verbose_name_plural': 'تقييمات المصادر',
            },
        ),
        migrations.CreateModel(
            name='RemediationPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(max_length=300, verbose_name='سبب الخطة')),
                ('recommendation', models.TextField(verbose_name='التوصية العلاجية')),
                ('status', models.CharField(choices=[('active', 'نشطة'), ('completed', 'مكتملة')], default='active', max_length=20, verbose_name='الحالة')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='remediation_plans', to='open_learning.learninglesson', verbose_name='الدرس')),
                ('quiz', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='remediation_plans', to='open_learning.lessonquiz', verbose_name='الاختبار')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='open_learning_remediation_plans', to='school.student', verbose_name='الطالب')),
            ],
            options={
                'verbose_name': 'خطة علاجية',
                'verbose_name_plural': 'الخطط العلاجية',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='guardianstudentlink',
            constraint=models.UniqueConstraint(fields=('guardian', 'student'), name='unique_guardian_student_link'),
        ),
        migrations.AddConstraint(
            model_name='learningachievement',
            constraint=models.UniqueConstraint(fields=('student', 'lesson', 'kind'), name='unique_student_lesson_achievement'),
        ),
        migrations.AddConstraint(
            model_name='learningresourcefavorite',
            constraint=models.UniqueConstraint(fields=('student', 'resource'), name='unique_student_resource_favorite'),
        ),
        migrations.AddConstraint(
            model_name='learningresourcerating',
            constraint=models.UniqueConstraint(fields=('student', 'resource'), name='unique_student_resource_rating'),
        ),
        migrations.AddConstraint(
            model_name='remediationplan',
            constraint=models.UniqueConstraint(fields=('student', 'quiz'), name='unique_student_quiz_remediation'),
        ),
    ]
