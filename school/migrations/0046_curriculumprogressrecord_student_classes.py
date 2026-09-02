from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0045_supervisorvisitfollowup'),
    ]

    operations = [
        migrations.AddField(
            model_name='curriculumprogressrecord',
            name='student_classes',
            field=models.ManyToManyField(blank=True, related_name='curriculum_multi_progress_records', to='school.class', verbose_name='الصفوف'),
        ),
    ]
