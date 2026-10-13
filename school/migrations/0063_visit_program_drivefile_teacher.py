from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0062_visit_program_drive_files'),
    ]

    operations = [
        migrations.AddField(
            model_name='visitprogramdrivefile',
            name='teacher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='visit_program_drive_files', to='school.teacher', verbose_name='المعلم المرتبط'),
        ),
    ]
