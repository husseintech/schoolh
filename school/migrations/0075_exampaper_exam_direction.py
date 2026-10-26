from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("school", "0074_exam_header_offsets"),
    ]

    operations = [
        migrations.AddField(
            model_name="exampaper",
            name="exam_direction",
            field=models.CharField(
                choices=[("rtl", "من اليمين لليسار"), ("ltr", "من اليسار لليمين")],
                default="rtl",
                max_length=3,
                verbose_name="اتجاه الاختبار",
            ),
        ),
    ]
