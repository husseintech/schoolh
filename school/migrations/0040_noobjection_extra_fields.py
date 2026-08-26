from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0039_remove_fixedlesson_unique_fixed_lesson_cell_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='noobjection',
            name='number',
            field=models.CharField(default='', max_length=50, blank=True, verbose_name='الرقم (للصادر)'),
        ),
        migrations.AddField(
            model_name='noobjection',
            name='date',
            field=models.DateField('التاريخ', default=datetime.date.today),
        ),
        migrations.AddField(
            model_name='noobjection',
            name='academic_year',
            field=models.CharField('العام الدراسي', default='', max_length=50, blank=True),
        ),
    ]
