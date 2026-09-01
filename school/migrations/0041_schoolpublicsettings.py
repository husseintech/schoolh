from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0040_noobjection_extra_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchoolPublicSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school_mobile', models.CharField(blank=True, max_length=30, verbose_name='رقم جوال المدرسة')),
                ('news_enabled', models.BooleanField(default=False, verbose_name='تفعيل شريط الأخبار')),
                ('news_source_name', models.CharField(blank=True, max_length=120, verbose_name='اسم مصدر الأخبار')),
                ('news_feed_url', models.URLField(blank=True, max_length=500, verbose_name='رابط RSS/Atom للأخبار')),
                ('school_info', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='public_settings', to='school.schoolinfo', verbose_name='بيانات المدرسة')),
            ],
            options={
                'verbose_name': 'إعدادات الواجهة العامة',
                'verbose_name_plural': 'إعدادات الواجهة العامة',
            },
        ),
    ]
