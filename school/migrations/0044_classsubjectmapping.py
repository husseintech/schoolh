from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('school', '0043_register_teacher_record_models')]

    operations = [
        migrations.CreateModel(
            name='ClassSubjectMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_class_subject_mappings', to='auth.user')),
                ('student_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subject_mappings', to='school.class', verbose_name='الصف')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_mappings', to='school.subject', verbose_name='المبحث')),
            ],
            options={
                'verbose_name': 'مادة صف',
                'verbose_name_plural': 'مواد الصفوف',
                'ordering': ['student_class__name', 'subject__name'],
            },
        ),
        migrations.AddConstraint(
            model_name='classsubjectmapping',
            constraint=models.UniqueConstraint(fields=('student_class', 'subject'), name='unique_class_subject_mapping'),
        ),
    ]
