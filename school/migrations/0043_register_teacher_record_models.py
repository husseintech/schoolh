# This project keeps some optional model classes outside school/models.py.
# Migration 0042 creates their database tables; this no-op migration is a stable marker for deployment ordering.
from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('school','0042_teacher_records')]
    operations=[]
