from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('school', '0079_support_education')]

    operations = [
        migrations.AddField(
            model_name='teacher',
            name='support_classes',
            field=models.ManyToManyField(blank=True, related_name='support_teachers', to='school.class', verbose_name='الصفوف المكلف بها كمساند'),
        ),
    ]
