from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('school', '0076_kindergarten_visit_report')]
    operations = [
        migrations.AddField(
            model_name='kindergartenvisitreport',
            name='school_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='اسم المدرسة'),
        ),
    ]
