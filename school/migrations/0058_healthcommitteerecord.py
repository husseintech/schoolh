# Generated for the school health committee module.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0057_warden_criteria'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='HealthCommitteeRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان السجل')),
                ('record_type', models.CharField(choices=[('meeting', 'اجتماعات اللجنة'), ('safety', 'فحص السلامة والبيئة المدرسية'), ('activity', 'الأنشطة الصحية والتثقيفية'), ('canteen', 'متابعة المقصف والتغذية'), ('reference', 'سجل مرجعي / ملاحظات عامة')], default='meeting', max_length=30, verbose_name='نوع السجل')),
                ('record_date', models.DateField(verbose_name='التاريخ')),
                ('status', models.CharField(choices=[('planned', 'مخطط له'), ('in_progress', 'قيد المتابعة'), ('completed', 'مكتمل'), ('deferred', 'مؤجل')], default='planned', max_length=20, verbose_name='حالة المتابعة')),
                ('location', models.CharField(blank=True, max_length=200, verbose_name='المكان')),
                ('participants', models.TextField(blank=True, verbose_name='الأعضاء / المشاركون')),
                ('details', models.TextField(blank=True, verbose_name='التفاصيل')),
                ('recommendations', models.TextField(blank=True, verbose_name='التوصيات والإجراءات المطلوبة')),
                ('responsible_person', models.CharField(blank=True, max_length=200, verbose_name='المسؤول عن المتابعة')),
                ('due_date', models.DateField(blank=True, null=True, verbose_name='موعد المتابعة')),
                ('outcome', models.TextField(blank=True, verbose_name='نتيجة المتابعة')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسجيل')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='health_committee_records_created', to=settings.AUTH_USER_MODEL, verbose_name='أُضيف بواسطة')),
            ],
            options={'verbose_name': 'سجل اللجنة الصحية', 'verbose_name_plural': 'سجلات اللجنة الصحية', 'ordering': ['-record_date', '-created_at']},
        ),
    ]
