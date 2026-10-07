from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0055_socialcommitteeexpense_socialcommitteepayment'),
    ]

    operations = [
        migrations.CreateModel(
            name='Warden',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=200, verbose_name='اسم الآذن')),
                ('id_number', models.CharField(max_length=50, unique=True, verbose_name='رقم الهوية')),
                ('specialization', models.CharField(blank=True, max_length=200, verbose_name='التخصص')),
                ('qualification_type', models.CharField(choices=[('university', 'جامعي'), ('non_university', 'غير جامعي')], max_length=20, verbose_name='نوع التخصص')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='رقم الهاتف')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='warden_profile', to='auth.user')),
            ],
            options={'verbose_name': 'آذن', 'verbose_name_plural': 'الآذنة', 'ordering': ['full_name']},
        ),
        migrations.CreateModel(
            name='WardenFollowup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('followup_date', models.DateField(verbose_name='تاريخ المتابعة')),
                ('classrooms_status', models.CharField(blank=True, choices=[('excellent', 'ممتاز'), ('good', 'جيد'), ('needs_followup', 'بحاجة إلى متابعة'), ('not_done', 'لم ينفذ')], max_length=30, verbose_name='نظافة الغرف الصفية وإفراغ سلات المهملات')),
                ('classrooms_notes', models.TextField(blank=True, verbose_name='ملاحظات الغرف الصفية')),
                ('yards_status', models.CharField(blank=True, choices=[('excellent', 'ممتاز'), ('good', 'جيد'), ('needs_followup', 'بحاجة إلى متابعة'), ('not_done', 'لم ينفذ')], max_length=30, verbose_name='تنظيف الساحات والملاعب والحديقة والمظلات')),
                ('yards_notes', models.TextField(blank=True, verbose_name='ملاحظات الساحات والملاعب')),
                ('staff_rooms_status', models.CharField(blank=True, choices=[('excellent', 'ممتاز'), ('good', 'جيد'), ('needs_followup', 'بحاجة إلى متابعة'), ('not_done', 'لم ينفذ')], max_length=30, verbose_name='تنظيف غرفة المعلمين والإدارة وغرفة المعلمات')),
                ('staff_rooms_notes', models.TextField(blank=True, verbose_name='ملاحظات الغرف الإدارية والمعلمين')),
                ('corridors_status', models.CharField(blank=True, choices=[('excellent', 'ممتاز'), ('good', 'جيد'), ('needs_followup', 'بحاجة إلى متابعة'), ('not_done', 'لم ينفذ')], max_length=30, verbose_name='تنظيف الممرات والطوابق وبيت الدرج ومتابعة سطح البناء')),
                ('corridors_notes', models.TextField(blank=True, verbose_name='ملاحظات الممرات والطوابق')),
                ('kindergarten_status', models.CharField(blank=True, choices=[('excellent', 'ممتاز'), ('good', 'جيد'), ('needs_followup', 'بحاجة إلى متابعة'), ('not_done', 'لم ينفذ')], max_length=30, verbose_name='نظافة الروضة وباقي مرافق المدرسة')),
                ('kindergarten_notes', models.TextField(blank=True, verbose_name='ملاحظات الروضة والمرافق')),
                ('sanitary_status', models.CharField(blank=True, choices=[('excellent', 'ممتاز'), ('good', 'جيد'), ('needs_followup', 'بحاجة إلى متابعة'), ('not_done', 'لم ينفذ')], max_length=30, verbose_name='نظافة الوحدات الصحية والمشارب ومدخل المدرسة والساحات')),
                ('sanitary_notes', models.TextField(blank=True, verbose_name='ملاحظات الوحدات الصحية والمدخل')),
                ('general_notes', models.TextField(blank=True, verbose_name='ملاحظات عامة')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسجيل')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user', verbose_name='سجل بواسطة')),
                ('warden', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='followups', to='school.warden', verbose_name='الآذن')),
            ],
            options={'verbose_name': 'متابعة آذن', 'verbose_name_plural': 'متابعات الآذنة', 'ordering': ['-followup_date', 'warden__full_name']},
        ),
        migrations.AddConstraint(
            model_name='wardenfollowup',
            constraint=models.UniqueConstraint(fields=('warden', 'followup_date'), name='unique_warden_followup_date'),
        ),
    ]
