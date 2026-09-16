from datetime import date

from django.db import migrations, models
import school.models


def populate_assessment_month(apps, schema_editor):
    StudentLevel = apps.get_model('school', 'StudentLevel')
    for level in StudentLevel.objects.only('id', 'created_at').iterator():
        created_at = level.created_at
        month = date(created_at.year, created_at.month, 1)
        StudentLevel.objects.filter(pk=level.pk).update(assessment_month=month)


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0053_curriculumlessonvideo'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentlevel',
            name='assessment_month',
            field=models.DateField(null=True, verbose_name='شهر التقييم'),
        ),
        migrations.RunPython(
            populate_assessment_month,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='studentlevel',
            name='assessment_month',
            field=models.DateField(default=school.models.current_month_start, verbose_name='شهر التقييم'),
        ),
        migrations.AlterModelOptions(
            name='studentlevel',
            options={
                'ordering': ['-assessment_month', '-created_at'],
                'verbose_name': 'مستوى طالب',
                'verbose_name_plural': 'مستويات الطلاب',
            },
        ),
    ]
