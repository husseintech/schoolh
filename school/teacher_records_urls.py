from django.urls import path
from . import teacher_records_views as v

urlpatterns = [
    path('curriculum/', v.curriculum_records, name='curriculum_records'),
    path('curriculum/print/', v.curriculum_records_print, name='curriculum_records_print'),
    path('curriculum/<int:record_id>/delete/', v.curriculum_record_delete, name='curriculum_record_delete'),
    path('training/', v.training_records, name='training_records'),
    path('training/print/', v.training_records_print, name='training_records_print'),
    path('training/<int:record_id>/delete/', v.training_record_delete, name='training_record_delete'),
]
