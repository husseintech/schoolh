from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("school", "0071_exampaper"),
    ]

    operations = [
        migrations.AddField(
            model_name="exampaper",
            name="header_font_size",
            field=models.FloatField(default=9, verbose_name="حجم خط الترويسة"),
        ),
        migrations.AddField(
            model_name="exampaper",
            name="header_font_weight",
            field=models.PositiveSmallIntegerField(default=400, verbose_name="سماكة خط الترويسة"),
        ),
    ]
