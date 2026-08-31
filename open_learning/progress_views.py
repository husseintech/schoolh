from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import LearningLesson
from .progress_models import StudentLessonProgress


def _student_of(request):
    try:
        return request.user.student_profile
    except Exception:
        return None


def _progress_table_ready():
    try:
        return StudentLessonProgress._meta.db_table in connection.introspection.table_names()
    except Exception:
        return False


def _student_lesson_or_404(student, lesson_id):
    return get_object_or_404(
        LearningLesson.objects.prefetch_related('student_classes'),
        pk=lesson_id,
        status='published',
        student_classes=student.student_class,
    )


@login_required
def student_progress_dashboard(request):
    student = _student_of(request)
    if not student:
        messages.error(request, 'هذه الصفحة مخصصة للطلاب')
        return redirect('open_learning_list')

    lessons = list(
        LearningLesson.objects
        .filter(student_classes=student.student_class, status='published')
        .select_related('subject', 'teacher')
        .prefetch_related('student_classes')
        .distinct()
    )
    ready = _progress_table_ready()
    progress_map = {}
    if ready and lessons:
        progress_map = {
            p.lesson_id: p
            for p in StudentLessonProgress.objects.filter(
                student=student,
                lesson_id__in=[lesson.id for lesson in lessons],
            )
        }

    completed = in_progress = not_started = 0
    for lesson in lessons:
        progress = progress_map.get(lesson.id)
        lesson.progress_record = progress
        lesson.progress_state = progress.status if progress else StudentLessonProgress.STATUS_NOT_STARTED
        if lesson.progress_state == StudentLessonProgress.STATUS_COMPLETED:
            completed += 1
        elif lesson.progress_state == StudentLessonProgress.STATUS_IN_PROGRESS:
            in_progress += 1
        else:
            not_started += 1

    total = len(lessons)
    completion_percentage = round((completed * 100 / total), 0) if total else 0
    return render(request, 'open_learning/student_progress_dashboard.html', {
        'student': student,
        'lessons': lessons,
        'progress_ready': ready,
        'total_lessons': total,
        'completed_lessons': completed,
        'in_progress_lessons': in_progress,
        'not_started_lessons': not_started,
        'completion_percentage': completion_percentage,
    })


@login_required
@require_POST
def student_lesson_start(request, lesson_id):
    student = _student_of(request)
    if not student:
        messages.error(request, 'هذه العملية مخصصة للطلاب')
        return redirect('open_learning_list')
    lesson = _student_lesson_or_404(student, lesson_id)
    if not _progress_table_ready():
        messages.warning(request, 'تتبع التقدم ما زال في وضع التجربة ولم يُفعّل على قاعدة البيانات بعد')
        return redirect('ol_student_progress')
    progress, _ = StudentLessonProgress.objects.get_or_create(student=student, lesson=lesson)
    progress.mark_started()
    messages.success(request, 'تم بدء الدرس وحفظ تقدمك')
    return redirect('open_learning_lesson_detail', lesson_id=lesson.id)


@login_required
@require_POST
def student_lesson_complete(request, lesson_id):
    student = _student_of(request)
    if not student:
        messages.error(request, 'هذه العملية مخصصة للطلاب')
        return redirect('open_learning_list')
    lesson = _student_lesson_or_404(student, lesson_id)
    if not _progress_table_ready():
        messages.warning(request, 'تتبع التقدم ما زال في وضع التجربة ولم يُفعّل على قاعدة البيانات بعد')
        return redirect('ol_student_progress')
    progress, _ = StudentLessonProgress.objects.get_or_create(student=student, lesson=lesson)
    progress.mark_completed()
    messages.success(request, 'أحسنت، تم تسجيل الدرس كمكتمل')
    return redirect('ol_student_progress')
