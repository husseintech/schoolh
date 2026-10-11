from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('school', '0058_healthcommitteerecord')]
    operations = [
        migrations.AddField(model_name='healthcommitteerecord', name='meeting_number', field=models.CharField(blank=True, max_length=40, verbose_name='رقم الاجتماع')),
        migrations.AddField(model_name='healthcommitteerecord', name='agenda', field=models.TextField(blank=True, verbose_name='جدول الأعمال')),
        migrations.AddField(model_name='healthcommitteerecord', name='decisions', field=models.TextField(blank=True, verbose_name='القرارات والتكليفات')),
        migrations.AddField(model_name='healthcommitteerecord', name='inspection_findings', field=models.TextField(blank=True, verbose_name='نتائج الفحص والملاحظات الصحية')),
        migrations.AddField(model_name='healthcommitteerecord', name='corrective_actions', field=models.TextField(blank=True, verbose_name='الإجراءات التصحيحية المنفذة أو المطلوبة')),
        migrations.AddField(model_name='healthcommitteerecord', name='activity_target', field=models.CharField(blank=True, max_length=200, verbose_name='الفئة المستهدفة بالنشاط')),
        migrations.AddField(model_name='healthcommitteerecord', name='activity_participants_count', field=models.PositiveIntegerField(blank=True, null=True, verbose_name='عدد المشاركين بالنشاط')),
    ]
