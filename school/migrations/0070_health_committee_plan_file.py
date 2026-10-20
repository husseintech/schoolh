from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("school", "0069_health_committee_drive_file"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HealthCommitteePlanFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("form_key", models.CharField(default="committee-minutes", max_length=60, unique=True, verbose_name="رمز النموذج")),
                ("file_name", models.CharField(max_length=300, verbose_name="اسم الخطة")),
                ("mime_type", models.CharField(blank=True, max_length=150, verbose_name="نوع الملف")),
                ("file_size", models.PositiveBigIntegerField(blank=True, null=True, verbose_name="حجم الملف")),
                ("google_drive_file_id", models.CharField(max_length=200, unique=True, verbose_name="معرّف ملف Google Drive")),
                ("google_drive_url", models.URLField(blank=True, max_length=1000, verbose_name="رابط Google Drive")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ رفع الخطة")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="health_committee_plan_files", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "خطة اللجنة الصحية", "verbose_name_plural": "خطة اللجنة الصحية"},
        ),
    ]
