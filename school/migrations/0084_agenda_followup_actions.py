from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0083_reciprocal_visit_subject_topic'),
    ]

    operations = [
        migrations.AddField(
            model_name='agenda',
            name='followup_actions',
            field=models.TextField(blank=True, verbose_name='آلية المتابعة والإجراءات المتبعة'),
        ),
    ]
