from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0046_curriculumprogressrecord_student_classes'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentsurvey',
            name='owns_personal_phone',
            field=models.BooleanField(blank=True, null=True, verbose_name='يمتلك جوالاً خاصاً به'),
        ),
        migrations.AddField(
            model_name='studentsurvey',
            name='parent_monitors_content',
            field=models.BooleanField(blank=True, null=True, verbose_name='يراقب ولي الأمر ما يشاهده باستمرار'),
        ),
        migrations.AddField(
            model_name='studentsurvey',
            name='phone_deprivation_difficulty',
            field=models.BooleanField(blank=True, null=True, verbose_name='صعوبة حرمان الطالب من الجوال'),
        ),
        migrations.AddField(
            model_name='studentsurvey',
            name='unusual_behavior_when_phone_removed',
            field=models.BooleanField(blank=True, null=True, verbose_name='تصرفات غريبة عند الحرمان من الجوال'),
        ),
    ]
