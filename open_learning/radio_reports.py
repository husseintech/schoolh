from collections import defaultdict

from django.db.models import Q

from school.arabic_sort import arabic_sort_key
from school.models import Student

from .models import SchoolRadioEntry


def build_radio_participation_report(*, date_from=None, date_to=None, query='', class_id=None, limit=None):
    """Return exact student participation counts without double-counting a student per broadcast."""
    entry_filters = {}
    entry_queryset = SchoolRadioEntry.objects.all()
    if date_from:
        entry_filters['schoolradioentry__event_date__gte'] = date_from
        entry_queryset = entry_queryset.filter(event_date__gte=date_from)
    if date_to:
        entry_filters['schoolradioentry__event_date__lte'] = date_to
        entry_queryset = entry_queryset.filter(event_date__lte=date_to)

    participation = defaultdict(lambda: {
        'presenter_entry_ids': set(),
        'participant_entry_ids': set(),
    })
    presenter_links = SchoolRadioEntry.presenters.through.objects.filter(
        **entry_filters
    ).values_list('student_id', 'schoolradioentry_id')
    participant_links = SchoolRadioEntry.participants.through.objects.filter(
        **entry_filters
    ).values_list('student_id', 'schoolradioentry_id')

    for student_id, entry_id in presenter_links:
        participation[student_id]['presenter_entry_ids'].add(entry_id)
    for student_id, entry_id in participant_links:
        participation[student_id]['participant_entry_ids'].add(entry_id)

    students = Student.objects.filter(pk__in=participation).select_related('student_class')
    clean_query = (query or '').strip()
    if clean_query:
        students = students.filter(Q(full_name__icontains=clean_query) | Q(student_id__icontains=clean_query))
    if class_id:
        students = students.filter(student_class_id=class_id)

    rows = []
    for student in students:
        stats = participation[student.pk]
        presenter_entries = stats['presenter_entry_ids']
        participant_entries = stats['participant_entry_ids']
        rows.append({
            'student': student,
            'presenter_count': len(presenter_entries),
            'participant_count': len(participant_entries),
            'total_count': len(presenter_entries | participant_entries),
        })

    rows.sort(key=lambda row: (
        -row['total_count'],
        -row['presenter_count'],
        arabic_sort_key(row['student'].full_name),
    ))
    top_student = rows[0] if rows else None
    summary = {
        'broadcast_count': entry_queryset.count(),
        'unique_student_count': len(rows),
        'participation_count': sum(row['total_count'] for row in rows),
        'presenter_count': sum(row['presenter_count'] for row in rows),
        'participant_count': sum(row['participant_count'] for row in rows),
        'top_student': top_student,
    }
    if limit is not None:
        rows = rows[:limit]
    summary['rows'] = rows
    return summary
