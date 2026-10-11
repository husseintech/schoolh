from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('school', '0059_healthcommitteerecord_details'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='HealthCommitteeOfficialForm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('form_key', models.CharField(db_index=True, max_length=60, verbose_name='رمز النموذج')),
                ('form_title', models.CharField(max_length=240, verbose_name='اسم النموذج')),
                ('source_page', models.PositiveSmallIntegerField(default=1, verbose_name='صفحة المصدر')),
                ('entry_date', models.DateField(blank=True, null=True, verbose_name='التاريخ')),
                ('data', models.JSONField(blank=True, default=dict, verbose_name='بيانات النموذج')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسجيل')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='health_committee_official_forms', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'نموذج اللجنة الصحية الرسمي', 'verbose_name_plural': 'نماذج اللجنة الصحية الرسمية', 'ordering': ['source_page', '-created_at']},
        ),
    ]
