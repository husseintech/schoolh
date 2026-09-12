from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0050_student_admin_messages'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentAssistantSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=True, verbose_name='تشغيل مساعد الطلاب')),
                ('educational_ai_enabled', models.BooleanField(default=True, verbose_name='تشغيل المساعدة التعليمية الذكية')),
                ('daily_ai_limit', models.PositiveSmallIntegerField(default=10, verbose_name='الحد اليومي للأسئلة الذكية لكل طالب')),
                ('welcome_message', models.CharField(default='سعداء بوجودك معنا، وأنا هنا لمساعدتك في الوصول إلى مهامك ودروسك وكل ما تحتاجه داخل المدرسة.', max_length=500, verbose_name='رسالة الترحيب')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'إعدادات مساعد الطلاب', 'verbose_name_plural': 'إعدادات مساعد الطلاب'},
        ),
        migrations.CreateModel(
            name='StudentAssistantKnowledge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=120, verbose_name='عنوان الإجابة')),
                ('keywords', models.CharField(help_text='افصل بين الكلمات أو العبارات بفاصلة، مثل: الدوام، الجرس، موعد الطابور', max_length=300, verbose_name='الكلمات المفتاحية')),
                ('answer', models.TextField(max_length=2000, verbose_name='الإجابة المعتمدة')),
                ('action_label', models.CharField(blank=True, max_length=80, verbose_name='عنوان الرابط')),
                ('action_url', models.CharField(blank=True, help_text='مثال: /open-learning/', max_length=300, verbose_name='الرابط الداخلي')),
                ('is_active', models.BooleanField(default=True, verbose_name='مفعّلة')),
                ('priority', models.PositiveSmallIntegerField(default=10, verbose_name='الأولوية')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'إجابة معتمدة لمساعد الطلاب', 'verbose_name_plural': 'إجابات مساعد الطلاب المعتمدة', 'ordering': ['-priority', 'title']},
        ),
        migrations.CreateModel(
            name='StudentAssistantLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.CharField(max_length=500, verbose_name='السؤال')),
                ('answer', models.TextField(blank=True, max_length=2500, verbose_name='الإجابة')),
                ('mode', models.CharField(choices=[('guided', 'إجابة من النظام'), ('knowledge', 'إجابة مدرسية معتمدة'), ('ai', 'إجابة تعليمية ذكية'), ('cache', 'إجابة ذكية محفوظة')], default='guided', max_length=20, verbose_name='نوع الإجابة')),
                ('success', models.BooleanField(default=True, verbose_name='نجحت')),
                ('estimated_tokens', models.PositiveIntegerField(blank=True, null=True, verbose_name='الرموز المقدّرة')),
                ('duration_ms', models.PositiveIntegerField(blank=True, null=True, verbose_name='المدة بالمللي ثانية')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='التاريخ')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assistant_logs', to='school.student', verbose_name='الطالب')),
            ],
            options={'verbose_name': 'سجل مساعد الطلاب', 'verbose_name_plural': 'سجل مساعد الطلاب', 'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='studentassistantlog',
            index=models.Index(fields=['student', '-created_at'], name='student_ai_student_created_idx'),
        ),
        migrations.AddIndex(
            model_name='studentassistantlog',
            index=models.Index(fields=['mode', '-created_at'], name='student_ai_mode_created_idx'),
        ),
    ]
