from django.conf import settings
from django.db import migrations, models
import django.utils.timezone
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("school","0065_teacherfollowupregistersettings"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="LibraryLoan", fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("borrower_name",models.CharField(max_length=200,verbose_name="اسم مستعير الكتاب")),
            ("book_title",models.CharField(max_length=250,verbose_name="اسم الكتاب")),
            ("classification_number",models.CharField(blank=True,max_length=100,verbose_name="رقم التصنيف")),
            ("loan_date",models.DateField(default=django.utils.timezone.localdate,verbose_name="تاريخ الإعارة")),
            ("due_date",models.DateField(blank=True,null=True,verbose_name="موعد الإعادة المحدد")),
            ("returned_date",models.DateField(blank=True,null=True,verbose_name="تاريخ إعادة الكتاب الفعلي")),
            ("notes",models.TextField(blank=True,verbose_name="ملاحظات")),
            ("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("created_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="library_loans_created",to=settings.AUTH_USER_MODEL,verbose_name="أُضيف بواسطة")),
        ],options={"verbose_name":"إعارة كتاب","verbose_name_plural":"إعارات الكتب","ordering":["-loan_date","borrower_name","book_title"]}),
        migrations.CreateModel(name="LabRegisterEntry",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("register_type",models.CharField(choices=[("science","سجل مختبر العلوم"),("computer","سجل مختبر الحاسوب")],db_index=True,max_length=20,verbose_name="نوع السجل")),
            ("entry_date",models.DateField(default=django.utils.timezone.localdate,verbose_name="التاريخ")),
            ("title",models.CharField(max_length=250,verbose_name="عنوان / موضوع")),("details",models.TextField(blank=True,verbose_name="التفاصيل")),("notes",models.TextField(blank=True,verbose_name="ملاحظات")),
            ("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("created_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="lab_register_entries",to=settings.AUTH_USER_MODEL,verbose_name="أُضيف بواسطة")),
        ],options={"verbose_name":"بيان سجل مختبر","verbose_name_plural":"بيانات سجلات المختبرات","ordering":["-entry_date","-created_at"]}),
    ]
