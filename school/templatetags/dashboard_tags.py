from datetime import timedelta

from django import template
from django.db.models import Count
from django.utils import timezone

from school.models import (
    Agenda,
    GuardianSummons,
    Note,
    StudentAbsence,
    StudentLateness,
    StudentLeave,
    StudentWarning,
)

register = template.Library()


@register.simple_tag
def dashboard_today():
    """Read-only aggregates for the administration dashboard.

    This tag intentionally performs no writes and requires no migration.
    """
    today = timezone.localdate()
    since = today - timedelta(days=30)

    repeated_absence = (
        StudentAbsence.objects.filter(absence_date__gte=since, absence_date__lte=today)
        .values('student_id')
        .annotate(total=Count('id'))
        .filter(total__gte=3)
        .count()
    )
    repeated_lateness = (
        StudentLateness.objects.filter(date__gte=since, date__lte=today)
        .values('student_id')
        .annotate(total=Count('id'))
        .filter(total__gte=3)
        .count()
    )

    data = {
        'absence': StudentAbsence.objects.filter(absence_date=today).count(),
        'lateness': StudentLateness.objects.filter(date=today).count(),
        'leaves': StudentLeave.objects.filter(leave_date=today).count(),
        'notes': Note.objects.filter(created_at__date=today).count(),
        'warnings': StudentWarning.objects.filter(created_at__date=today).count(),
        'summons': GuardianSummons.objects.filter(created_at__date=today).count(),
        'pending_agenda': Agenda.objects.filter(is_completed=False).count(),
        'overdue_agenda': Agenda.objects.filter(is_completed=False, due_date__lt=today).count(),
        'repeated_absence': repeated_absence,
        'repeated_lateness': repeated_lateness,
    }
    data['attention_total'] = (
        data['overdue_agenda']
        + data['repeated_absence']
        + data['repeated_lateness']
        + data['warnings']
        + data['summons']
    )
    return data
