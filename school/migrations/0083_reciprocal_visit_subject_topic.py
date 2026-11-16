from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0082_support_teacher_attendance'),
    ]

    operations = [
        migrations.AddField(
            model_name='reciprocalvisit',
            name='subject_topic',
            field=models.CharField(blank=True, max_length=200, verbose_name='المادة أو موضوع الحصة'),
        ),
    ]
