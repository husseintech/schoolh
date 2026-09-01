from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import Class, SchoolInfo, Subject, TeacherScheduleEntry


def _to_int(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _percentage(passed, total):
    if total <= 0:
        return Decimal('0.00')
    try:
        return (Decimal(passed) * Decimal('100') / Decimal(total)).quantize(Decimal('0.01'))
    except (InvalidOperation, ZeroDivisionError):
        return Decimal('0.00')


def _scope_for_user(user):
    """Return the classes the user may analyse plus schedule/teacher scope."""
    role = user.profile.role
    if role not in ('admin', 'vice_principal', 'teacher'):
        return Class.objects.none(), TeacherScheduleEntry.objects.none(), None

    schedule = TeacherScheduleEntry.objects.filter(subject__isnull=False, student_class__isnull=False)
    teacher = getattr(user, 'teacher_profile', None)

    if role == 'teacher':
        if not teacher:
            return Class.objects.none(), TeacherScheduleEntry.objects.none(), None
        # Teacher class assignments are managed directly on Teacher.classes.
        # Do not require a generated daily schedule just to expose those classes.
        classes = teacher.classes.all().order_by('name')
        return classes, schedule.filter(teacher=teacher), teacher

    # For administration, expose classes that are actually assigned to at least one teacher.
    classes = Class.objects.filter(teachers__isnull=False).distinct().order_by('name')
    return classes, schedule, teacher


def _subjects_for_class(user, selected_class, schedule_scope, teacher):
    role = user.profile.role
    if role == 'teacher':
        # Prefer exact teacher+class subject mapping from the daily schedule when present.
        subject_ids = schedule_scope.filter(student_class=selected_class).values_list('subject_id', flat=True).distinct()
        subjects = Subject.objects.filter(id__in=subject_ids).order_by('name')
        if subjects.exists():
            return subjects
        # If the daily schedule has not been built yet, use the subjects already assigned
        # to this teacher in the teacher profile so assigned classes still work.
        return teacher.subjects.all().order_by('name') if teacher else Subject.objects.none()

    # Administration: prefer schedule mappings; otherwise derive from teachers assigned to class.
    subject_ids = schedule_scope.filter(student_class=selected_class).values_list('subject_id', flat=True).distinct()
    subjects = Subject.objects.filter(id__in=subject_ids).order_by('name')
    if subjects.exists():
        return subjects
    return Subject.objects.filter(teachers__classes=selected_class).distinct().order_by('name')


@login_required
def academic_achievement_report(request):
    """Printable achievement analysis scoped to teacher/class/subject assignments."""
    classes, schedule_scope, teacher = _scope_for_user(request.user)
    if request.user.profile.role not in ('admin', 'vice_principal', 'teacher'):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذا التقرير')
        return redirect('dashboard')

    selected_class = None
    total_students = 0
    subjects = Subject.objects.none()

    class_id = request.GET.get('class_id') or request.POST.get('class_id')
    if class_id:
        try:
            selected_class = classes.get(pk=class_id)
            total_students = selected_class.students.count()
            subjects = _subjects_for_class(request.user, selected_class, schedule_scope, teacher)
        except (Class.DoesNotExist, ValueError):
            selected_class = None
            messages.error(request, 'هذا الصف غير مرتبط بك أو غير متاح لك')

    if request.method == 'POST':
        if not selected_class:
            messages.error(request, 'يرجى اختيار الصف/الشعبة')
            return redirect('academic_achievement_report')
        if not subjects.exists():
            messages.error(request, 'لا توجد مواد مرتبطة بهذا الصف والمعلم')
            return redirect(f'/administration/academic-achievement/?class_id={selected_class.id}')

        rows = []
        for subject in subjects:
            half_passed = _to_int(request.POST.get(f'half_passed_{subject.id}'))
            half_failed = _to_int(request.POST.get(f'half_failed_{subject.id}'))
            final_passed = _to_int(request.POST.get(f'final_passed_{subject.id}'))
            final_failed = _to_int(request.POST.get(f'final_failed_{subject.id}'))

            if half_passed + half_failed > total_students or final_passed + final_failed > total_students:
                messages.error(request, f'مجموع الناجحين والراسبين في مبحث {subject.name} أكبر من عدد طلبة الصف')
                return render(request, 'school/academic_achievement_form.html', {
                    'classes': classes,
                    'subjects': subjects,
                    'selected_class': selected_class,
                    'total_students': total_students,
                    'school_year': request.POST.get('school_year', ''),
                    'semester': request.POST.get('semester', ''),
                    'is_teacher': request.user.profile.role == 'teacher',
                    'teacher': teacher,
                })

            half_percentage = _percentage(half_passed, total_students)
            final_percentage = _percentage(final_passed, total_students)
            rows.append({
                'subject': subject,
                'half_passed': half_passed,
                'half_failed': half_failed,
                'half_percentage': half_percentage,
                'final_passed': final_passed,
                'final_failed': final_failed,
                'final_percentage': final_percentage,
                'percentage_difference': final_percentage - half_percentage,
                'recommendation': request.POST.get(f'recommendation_{subject.id}', '').strip(),
            })

        return render(request, 'school/academic_achievement_print.html', {
            'info': SchoolInfo.objects.first(),
            'selected_class': selected_class,
            'total_students': total_students,
            'school_year': request.POST.get('school_year', '').strip(),
            'semester': request.POST.get('semester', '').strip(),
            'rows': rows,
            'teacher': teacher,
        })

    return render(request, 'school/academic_achievement_form.html', {
        'classes': classes,
        'subjects': subjects,
        'selected_class': selected_class,
        'total_students': total_students,
        'is_teacher': request.user.profile.role == 'teacher',
        'teacher': teacher,
    })
