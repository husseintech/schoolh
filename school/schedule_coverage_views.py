from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden

from .models import Teacher, TeacherScheduleEntry, has_perm


SCHEDULE_DAYS = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس']
SCHEDULE_PERIODS = range(1, 8)


def _schedule_data():
    teachers = list(Teacher.objects.all().order_by('full_name'))
    entries = list(
        TeacherScheduleEntry.objects.select_related('teacher', 'subject', 'student_class')
        .all()
    )
    by_teacher_cell = {(e.teacher_id, e.day, e.period): e for e in entries}
    class_cells = defaultdict(list)
    for entry in entries:
        if entry.student_class_id:
            class_cells[(entry.day, entry.period, entry.student_class_id)].append(entry)
    return teachers, entries, by_teacher_cell, class_cells


def _is_free(teacher_id, day, period, by_teacher_cell):
    return (teacher_id, day, period) not in by_teacher_cell


def _rank_candidates(subject, student_class, day, period, teachers, by_teacher_cell, class_cells, excluded_ids=None, ignore_entry_id=None):
    excluded_ids = set(excluded_ids or ())
    # The absent teacher's original lesson occupies this class slot in the
    # source timetable, but it is precisely the lesson being replaced.
    # Any other existing lesson for the same class still blocks the slot.
    if student_class:
        occupied = class_cells.get((day, period, student_class.id), [])
        if any(item.id != ignore_entry_id for item in occupied):
            return []
    candidates = []
    for teacher in teachers:
        if teacher.id in excluded_ids or not _is_free(teacher.id, day, period, by_teacher_cell):
            continue
        teaches_subject = bool(subject and teacher.subjects.filter(pk=subject.pk).exists())
        teaches_class = bool(student_class and teacher.classes.filter(pk=student_class.pk).exists())
        if teaches_subject and teaches_class:
            priority = 0
        elif teaches_subject:
            priority = 1
        else:
            priority = 2
        candidates.append((priority, teacher.full_name.casefold(), teacher))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in candidates]


@login_required
def schedule_available_report(request):
    if not has_perm(request.user, 'schedule', 'view'):
        return HttpResponseForbidden('ليس لديك صلاحية عرض الجدول أو خطة التغطية.')
    teachers, entries, by_teacher_cell, _ = _schedule_data()
    availability = []
    for day in SCHEDULE_DAYS:
        day_rows = []
        for period in SCHEDULE_PERIODS:
            free_names = [
                teacher.full_name for teacher in teachers
                if _is_free(teacher.id, day, period, by_teacher_cell)
            ]
            day_rows.append({'period': period, 'teachers': free_names})
        availability.append({'day': day, 'periods': day_rows})
    return render(request, 'school/schedule_available_report.html', {
        'availability': availability,
        'teacher_count': len(teachers),
        'periods': SCHEDULE_PERIODS,
        'days': SCHEDULE_DAYS,
    })


@login_required
def schedule_absence_coverage(request):
    if not has_perm(request.user, 'schedule', 'view'):
        return render(request, 'school/permission_denied.html', status=403)
    teachers, entries, by_teacher_cell, class_cells = _schedule_data()
    selected_teacher_id = request.POST.get('teacher_id') or request.GET.get('teacher_id', '')
    selected_day = request.POST.get('day') or request.GET.get('day', SCHEDULE_DAYS[0])
    plan = []
    if request.method == 'POST' and has_perm(request.user, 'schedule', 'add'):
        absent = next((t for t in teachers if str(t.id) == str(selected_teacher_id)), None)
        if absent and selected_day in SCHEDULE_DAYS:
            absent_entries = sorted(
                [e for e in entries if e.teacher_id == absent.id and e.day == selected_day],
                key=lambda e: e.period,
            )
            for entry in absent_entries:
                candidates = _rank_candidates(
                    entry.subject, entry.student_class, selected_day, entry.period,
                    teachers, by_teacher_cell, class_cells,
                    excluded_ids={absent.id}, ignore_entry_id=entry.id,
                )
                if candidates:
                    chosen = candidates[0]
                    same_class_subject = bool(
                        entry.subject and entry.student_class
                        and chosen.subjects.filter(pk=entry.subject_id).exists()
                        and chosen.classes.filter(pk=entry.student_class_id).exists()
                    )
                    plan.append({
                        'period': entry.period,
                        'subject': entry.subject.name if entry.subject else 'غير محددة',
                        'class_name': entry.student_class.name if entry.student_class else 'غير محدد',
                        'action': 'cover',
                        'teacher': chosen.full_name,
                        'priority_label': 'المادة نفسها والصف نفسه' if same_class_subject else (
                            'المادة نفسها، معلم متاح' if entry.subject and chosen.subjects.filter(pk=entry.subject_id).exists()
                            else 'معلم متاح عند الضرورة'
                        ),
                        'note': 'تغطية مقترحة دون تعديل الجدول الأصلي.',
                    })
                    continue

                # If direct coverage is impossible, try moving the final-period lesson
                # into an earlier empty slot for the class, then end the class day early.
                moved = None
                is_last_class_period = bool(entry.student_class) and not any(
                    class_cells.get((selected_day, later_period, entry.student_class_id))
                    for later_period in range(entry.period + 1, 8)
                )
                if is_last_class_period and entry.student_class and entry.subject and entry.period > 1:
                    for earlier_period in range(entry.period - 1, 0, -1):
                        if class_cells.get((selected_day, earlier_period, entry.student_class_id)):
                            continue
                        earlier_candidates = _rank_candidates(
                            entry.subject, entry.student_class, selected_day, earlier_period,
                            teachers, by_teacher_cell, class_cells, excluded_ids={absent.id},
                        )
                        if earlier_candidates:
                            candidate = earlier_candidates[0]
                            moved = (earlier_period, candidate)
                            break
                if moved:
                    new_period, chosen = moved
                    plan.append({
                        'period': entry.period,
                        'subject': entry.subject.name if entry.subject else 'غير محددة',
                        'class_name': entry.student_class.name if entry.student_class else 'غير محدد',
                        'action': 'move',
                        'teacher': chosen.full_name,
                        'new_period': new_period,
                        'priority_label': 'تقديم الحصة إلى وقت فراغ سابق',
                        'note': f'اقتراح نقل الحصة إلى الحصة {new_period} وإنهاء دوام الصف بدل إبقائه حتى الحصة {entry.period}. لم يُعدّل أي جدول.',
                    })
                elif is_last_class_period and entry.student_class and entry.period > 1:
                    plan.append({
                        'period': entry.period,
                        'subject': entry.subject.name if entry.subject else 'غير محددة',
                        'class_name': entry.student_class.name,
                        'action': 'dismiss',
                        'teacher': '',
                        'priority_label': 'تعذر إيجاد بديل أو وقت تقديم مناسب',
                        'note': f'يمكن اعتماد إنهاء دوام الصف بعد الحصة {entry.period - 1} إذا وافقت الإدارة؛ الحصة غير مغطاة.',
                    })
                else:
                    plan.append({
                        'period': entry.period,
                        'subject': entry.subject.name if entry.subject else 'غير محددة',
                        'class_name': entry.student_class.name if entry.student_class else 'غير محدد',
                        'action': 'uncovered',
                        'teacher': '',
                        'priority_label': 'تحتاج قرار الإدارة',
                        'note': 'لم يُعثر على معلم متاح أو وقت سابق مناسب دون تعارض.',
                    })
    return render(request, 'school/schedule_absence_coverage.html', {
        'teachers': teachers,
        'days': SCHEDULE_DAYS,
        'selected_teacher_id': str(selected_teacher_id),
        'selected_day': selected_day,
        'plan': plan,
        'has_results': request.method == 'POST',
        'can_plan': has_perm(request.user, 'schedule', 'add'),
    })
