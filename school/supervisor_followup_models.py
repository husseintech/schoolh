from django.contrib.auth.models import User
from django.db import models

from .models import SupervisorVisit


class SupervisorVisitFollowup(models.Model):
    visit = models.OneToOneField(
        SupervisorVisit,
        on_delete=models.CASCADE,
        related_name='management_followup',
        verbose_name='زيارة المشرف',
    )
    followup_date = models.DateField('تاريخ متابعة الإدارة')
    notes = models.TextField('متابعة الإدارة')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervisor_visit_followups',
        verbose_name='سجل بواسطة',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'متابعة زيارة مشرف'
        verbose_name_plural = 'متابعات زيارات المشرفين'
        ordering = ['-followup_date', '-updated_at']

    def __str__(self):
        return f'{self.visit.teacher.full_name} - {self.followup_date}'
