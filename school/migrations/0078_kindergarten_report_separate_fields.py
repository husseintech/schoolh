from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0077_kindergarten_report_school_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='kindergartenvisitreport',
            name='scientific_qualification',
            field=models.CharField(blank=True, choices=[('دبلوم', 'دبلوم'), ('بكالوريوس', 'بكالوريوس'), ('ماجستير', 'ماجستير'), ('دكتوراه', 'دكتوراه')], max_length=30, verbose_name='المؤهل العلمي'),
        ),
        migrations.AddField(
            model_name='kindergartenvisitreport',
            name='professional_qualification',
            field=models.CharField(blank=True, choices=[('دبلوم تأهيل تربوي', 'دبلوم تأهيل تربوي'), ('تأهيل رياض أطفال', 'تأهيل رياض أطفال'), ('دورات تربوية', 'دورات تربوية'), ('أخرى', 'أخرى')], max_length=100, verbose_name='المؤهل المسلكي'),
        ),
        migrations.AddField(
            model_name='kindergartenvisitreport',
            name='whole_group_count',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='عدد المجموعة الكلية'),
        ),
        migrations.AddField(
            model_name='kindergartenvisitreport',
            name='small_group_count',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='عدد المجموعة المصغرة'),
        ),
    ]
