from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0063_visit_program_drivefile_teacher'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='display_order',
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text='يحفظ ترتيب الطالب الوارد في ملف Excel المعتمد',
                verbose_name='ترتيب الطالب المعتمد',
            ),
        ),
    ]
