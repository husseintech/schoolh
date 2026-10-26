from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("school", "0073_examfont_header_controls"),
    ]

    operations = [
        migrations.AddField(
            model_name="exampaper",
            name="header_left_offset",
            field=models.SmallIntegerField(default=0, verbose_name="إزاحة القسم الأيسر للترويسة"),
        ),
        migrations.AddField(
            model_name="exampaper",
            name="header_right_offset",
            field=models.SmallIntegerField(default=0, verbose_name="إزاحة القسم الأيمن للترويسة"),
        ),
    ]
