from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("school", "0066_school_registers")]

    operations = [
        migrations.AddField(
            model_name="labregisterentry",
            name="day",
            field=models.CharField(blank=True, max_length=30, verbose_name="اليوم"),
        ),
        migrations.AddField(
            model_name="labregisterentry",
            name="grade",
            field=models.CharField(blank=True, max_length=100, verbose_name="الصف"),
        ),
        migrations.AddField(
            model_name="labregisterentry",
            name="session_title",
            field=models.CharField(blank=True, max_length=250, verbose_name="عنوان الحصة"),
        ),
        migrations.AddField(
            model_name="labregisterentry",
            name="programs_used",
            field=models.TextField(blank=True, verbose_name="البرامج المستخدمة"),
        ),
        migrations.AddField(
            model_name="labregisterentry",
            name="objectives_activities",
            field=models.TextField(blank=True, verbose_name="الأهداف والأنشطة"),
        ),
        migrations.AddField(
            model_name="labregisterentry",
            name="teacher_name",
            field=models.CharField(blank=True, max_length=200, verbose_name="المعلم"),
        ),
        migrations.AddField(
            model_name="labregisterentry",
            name="lab_supervisor_notes",
            field=models.TextField(blank=True, verbose_name="ملاحظات مشرف المختبر"),
        ),
        migrations.AddField(
            model_name="labregisterentry",
            name="director_notes",
            field=models.TextField(blank=True, verbose_name="ملاحظات المدير"),
        ),
    ]
