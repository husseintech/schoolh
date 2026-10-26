# Generated for the school exam writer feature.
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("school", "0070_health_committee_plan_file"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExamPaper",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("exam_name", models.CharField(max_length=200, verbose_name="اسم الاختبار")),
                ("duration_minutes", models.PositiveSmallIntegerField(default=40, validators=[django.core.validators.MinValueValidator(1)], verbose_name="مدة الاختبار بالدقائق")),
                ("exam_type", models.CharField(blank=True, max_length=100, verbose_name="نوع الاختبار")),
                ("questions", models.JSONField(blank=True, default=list, verbose_name="الأسئلة")),
                ("font_name", models.CharField(default="Traditional Arabic", max_length=80, verbose_name="نوع الخط")),
                ("font_size", models.PositiveSmallIntegerField(default=16, verbose_name="حجم الخط")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تعديل")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_exam_papers", to="auth.user", verbose_name="أنشئ بواسطة")),
                ("subject", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_papers", to="school.subject", verbose_name="المبحث")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exam_papers", to="school.teacher", verbose_name="المعلم")),
                ("classes", models.ManyToManyField(related_name="exam_papers", to="school.class", verbose_name="الصفوف والشعب")),
            ],
            options={
                "verbose_name": "اختبار مكتوب",
                "verbose_name_plural": "الاختبارات المكتوبة",
                "ordering": ["-updated_at"],
            },
        ),
    ]
