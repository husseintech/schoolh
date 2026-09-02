from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render

from .models import Class, SchoolInfo, Teacher, TeacherScheduleEntry


@login_required
def teaching_load_distribution(request):
    """Read-only administration report derived entirely from the saved teacher schedule."""
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    if role not in ('admin', 'vice_principal'):
        messages.error(request, 'ليس لديك صلاحية لعرض توزيع الأنصبة')
        return redirect('dashboard')

    scheduled_classes = list(
        Class.objects.filter(
            schedule_entries__subject__isnull=False,
            schedule_entries__teacher__isnull=False,
        ).distinct().order_by('name')
    )
    classes = scheduled_classes or list(Class.objects.all().order_by('name'))

    aggregate_rows = (
        TeacherScheduleEntry.objects
        .filter(subject__isnull=False, student_class__isnull=False)
        .values(
            'teacher_id',
            'student_class_id',
            'subject_id',
            'subject__name',
        )
        .annotate(lesson_count=Count('id'))
        .order_by('teacher_id', 'student_class_id', 'subject__name')
    )

    by_teacher = defaultdict(lambda: defaultdict(list))
    teacher_totals = defaultdict(int)
    for row in aggregate_rows:
        item = {
            'subject_id': row['subject_id'],
            'subject_name': row['subject__name'],
            'count': row['lesson_count'],
        }
        by_teacher[row['teacher_id']][row['student_class_id']].append(item)
        teacher_totals[row['teacher_id']] += row['lesson_count']

    teacher_rows = []
    for index, teacher in enumerate(Teacher.objects.all().order_by('full_name'), start=1):
        class_cells = []
        for student_class in classes:
            entries = by_teacher[teacher.id].get(student_class.id, [])
            class_cells.append({
                'class': student_class,
                'entries': entries,
                'class_total': sum(item['count'] for item in entries),
            })
        teacher_rows.append({
            'index': index,
            'teacher': teacher,
            'class_cells': class_cells,
            'total': teacher_totals.get(teacher.id, 0),
        })

    return render(request, 'school/teaching_load_distribution.html', {
        'info': SchoolInfo.objects.first(),
        'classes': classes,
        'teacher_rows': teacher_rows,
    })
