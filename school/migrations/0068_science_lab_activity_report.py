from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("school", "0067_computer_lab_notebook_fields")]

    operations = [
        migrations.AddField("labregisterentry", "activity_number", models.CharField(blank=True, max_length=50, verbose_name="رقم النشاط")),
        migrations.AddField("labregisterentry", "semester", models.CharField(blank=True, max_length=50, verbose_name="الفصل الدراسي")),
        migrations.AddField("labregisterentry", "student_count", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="عدد الطلبة")),
        migrations.AddField("labregisterentry", "section", models.CharField(blank=True, max_length=50, verbose_name="الشعبة")),
        migrations.AddField("labregisterentry", "unit_lesson", models.TextField(blank=True, verbose_name="الوحدة والدرس")),
        migrations.AddField("labregisterentry", "learning_outcomes", models.TextField(blank=True, verbose_name="نتاجات التعلم والأهداف")),
        migrations.AddField("labregisterentry", "tools_materials", models.TextField(blank=True, verbose_name="الأدوات والمواد المستخدمة")),
        migrations.AddField("labregisterentry", "safety_procedures", models.TextField(blank=True, verbose_name="إجراءات السلامة")),
        migrations.AddField("labregisterentry", "implementation_steps", models.TextField(blank=True, verbose_name="خطوات التنفيذ")),
        migrations.AddField("labregisterentry", "actual_observations", models.TextField(blank=True, verbose_name="الملاحظات والبيانات الفعلية")),
        migrations.AddField("labregisterentry", "results_conclusion", models.TextField(blank=True, verbose_name="النتائج والاستنتاج")),
        migrations.AddField("labregisterentry", "assessment", models.TextField(blank=True, verbose_name="مدى تحقق الأهداف وتقويم الطلبة")),
        migrations.AddField("labregisterentry", "incidents_actions", models.TextField(blank=True, verbose_name="الصعوبات أو الحوادث والإجراء المتخذ")),
        migrations.AddField("labregisterentry", "followup_activity", models.TextField(blank=True, verbose_name="المتابعة والنشاط العلاجي أو الإثرائي")),
    ]
