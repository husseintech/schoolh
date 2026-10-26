from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("school", "0072_exampaper_header_typography"),
    ]

    operations = [
        migrations.AddField(
            model_name="exampaper",
            name="header_font_family",
            field=models.CharField(default="Traditional Arabic", max_length=80, verbose_name="خط الترويسة"),
        ),
        migrations.AddField(
            model_name="exampaper",
            name="header_text_align",
            field=models.CharField(default="center", max_length=10, verbose_name="محاذاة الترويسة"),
        ),
        migrations.AddField(
            model_name="exampaper",
            name="header_line_height",
            field=models.FloatField(default=1.3, verbose_name="ارتفاع سطر الترويسة"),
        ),
        migrations.AddField(
            model_name="exampaper",
            name="header_letter_spacing",
            field=models.FloatField(default=0, verbose_name="تباعد حروف الترويسة"),
        ),
        migrations.AddField(
            model_name="exampaper",
            name="header_padding",
            field=models.FloatField(default=0, verbose_name="المسافة الداخلية للترويسة"),
        ),
        migrations.CreateModel(
            name="ExamFont",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="اسم الخط")),
                ("file", models.FileField(upload_to="exam_fonts/", verbose_name="ملف الخط")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الرفع")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_exam_fonts", to="auth.user")),
            ],
            options={
                "verbose_name": "خط الاختبارات",
                "verbose_name_plural": "خطوط الاختبارات",
                "ordering": ["name"],
            },
        ),
    ]
