from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('school', '0084_agenda_followup_actions')]

    operations = [
        migrations.AddField(
            model_name='agenda',
            name='completion_note',
            field=models.TextField(blank=True, verbose_name='كيف تم الإنجاز؟'),
        ),
    ]
