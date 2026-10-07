from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0056_warden_followup'),
    ]

    operations = [
        migrations.AddField(
            model_name='warden',
            name='criteria',
            field=models.JSONField(blank=True, default=list, verbose_name='بنود المتابعة'),
        ),
        migrations.AddField(
            model_name='wardenfollowup',
            name='evaluation_data',
            field=models.JSONField(blank=True, default=list, verbose_name='نتائج البنود'),
        ),
    ]
