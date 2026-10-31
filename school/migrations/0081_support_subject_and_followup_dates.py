from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0080_support_teacher_class_assignments'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportlessonassignment',
            name='subject',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='support_assignments',
                to='school.subject',
                verbose_name='المبحث',
            ),
        ),
        migrations.AddField(
            model_name='supportlessonassignment',
            name='assignment_date',
            field=models.DateField(default=django.utils.timezone.localdate, db_index=True, verbose_name='تاريخ المتابعة'),
        ),
        migrations.AlterField(
            model_name='supportlessonexecution',
            name='execution_date',
            field=models.DateField(default=django.utils.timezone.localdate, verbose_name='تاريخ المتابعة'),
        ),
        migrations.AlterField(
            model_name='supportlessonexecution',
            name='lesson_period',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='رقم الحصة'),
        ),
    ]
