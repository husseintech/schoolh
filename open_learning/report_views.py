from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Max, Min
from django.shortcuts import get_object_or_404, redirect, render

from school.models import Student

from .learning_models import (
    LessonQuiz, QuizAttempt,
    LessonAssignment, AssignmentSubmission,
    LessonActivity, StudentActivityCompletion,
)
from .learning_views import learning_suite_ready
from .views import _can_manage


def _lesson_students(lesson):
    class_ids = list(lesson.student_classes.values_list('id', flat=True))
    return list(
        Student.objects.filter(student_class_id__in=class_ids)
        .select_related('student_class')
        .order_by('student_class__name', 'full_name')
    )


@login_required
def quiz_results_report(request, quiz_id):
    """تقرير صفّي لاختبار واحد: جميع طلاب الصفوف المستهدفة وعلاماتهم."""
    if not learning_suite_ready():
        messages.warning(request, 'حزمة التعلم لم تُفعّل بعد على قاعدة البيانات.')
        return redirect('open_learning_list')

    quiz = get_object_or_404(
        LessonQuiz.objects.select_related('lesson', 'lesson__subject', 'lesson__teacher')
        .prefetch_related('lesson__student_classes'),
        pk=quiz_id,
    )
    lesson = quiz.lesson
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية لعرض نتائج هذا الاختبار')
        return redirect('open_learning_list')

    students = _lesson_students(lesson)
    attempts = QuizAttempt.objects.filter(quiz=quiz, student_id__in=[s.id for s in students])
    attempts_by_student = {}
    for attempt in attempts.order_by('student_id', '-submitted_at'):
        attempts_by_student.setdefault(attempt.student_id, []).append(attempt)

    rows = []
    for student in students:
        student_attempts = attempts_by_student.get(student.id, [])
        latest = student_attempts[0] if student_attempts else None
        best = max(student_attempts, key=lambda a: a.percentage) if student_attempts else None
        rows.append({
            'student': student,
            'attempt_count': len(student_attempts),
            'latest': latest,
            'best': best,
        })

    stats = attempts.aggregate(
        average=Avg('percentage'),
        highest=Max('percentage'),
        lowest=Min('percentage'),
    )
    attempted_students = attempts.values('student_id').distinct().count()
    passed_students = attempts.filter(passed=True).values('student_id').distinct().count()

    return render(request, 'open_learning/quiz_results_report.html', {
        'quiz': quiz,
        'lesson': lesson,
        'rows': rows,
        'total_students': len(students),
        'attempted_students': attempted_students,
        'not_attempted_students': max(0, len(students) - attempted_students),
        'passed_students': passed_students,
        'average': stats['average'],
        'highest': stats['highest'],
        'lowest': stats['lowest'],
    })


@login_required
def assignment_results_report(request, assignment_id):
    """تقرير واجب واحد: جميع طلاب الصف وحالة التسليم والدرجة."""
    if not learning_suite_ready():
        messages.warning(request, 'حزمة التعلم لم تُفعّل بعد على قاعدة البيانات.')
        return redirect('open_learning_list')

    assignment = get_object_or_404(
        LessonAssignment.objects.select_related('lesson', 'lesson__subject', 'lesson__teacher')
        .prefetch_related('lesson__student_classes'),
        pk=assignment_id,
    )
    lesson = assignment.lesson
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية لعرض تسليمات هذا الواجب')
        return redirect('open_learning_list')

    students = _lesson_students(lesson)
    submissions = AssignmentSubmission.objects.filter(
        assignment=assignment, student_id__in=[s.id for s in students]
    ).select_related('student')
    submission_map = {s.student_id: s for s in submissions}

    rows = [{'student': student, 'submission': submission_map.get(student.id)} for student in students]
    graded = submissions.exclude(grade__isnull=True)
    stats = graded.aggregate(average=Avg('grade'), highest=Max('grade'), lowest=Min('grade'))

    return render(request, 'open_learning/assignment_results_report.html', {
        'assignment': assignment,
        'lesson': lesson,
        'rows': rows,
        'total_students': len(students),
        'submitted_students': submissions.count(),
        'not_submitted_students': max(0, len(students) - submissions.count()),
        'reviewed_students': submissions.filter(status='reviewed').count(),
        'graded_students': graded.count(),
        'average': stats['average'],
        'highest': stats['highest'],
        'lowest': stats['lowest'],
    })


@login_required
def activity_results_report(request, activity_id):
    """تقرير نشاط واحد: جميع طلاب الصف وحالة الإكمال وتاريخه."""
    if not learning_suite_ready():
        messages.warning(request, 'حزمة التعلم لم تُفعّل بعد على قاعدة البيانات.')
        return redirect('open_learning_list')

    activity = get_object_or_404(
        LessonActivity.objects.select_related('lesson', 'lesson__subject', 'lesson__teacher')
        .prefetch_related('lesson__student_classes'),
        pk=activity_id,
    )
    lesson = activity.lesson
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية لعرض متابعة هذا النشاط')
        return redirect('open_learning_list')

    students = _lesson_students(lesson)
    completions = StudentActivityCompletion.objects.filter(
        activity=activity, student_id__in=[s.id for s in students]
    ).select_related('student')
    completion_map = {c.student_id: c for c in completions}
    completed_count = completions.count()
    completion_percent = round((completed_count * 100 / len(students)), 1) if students else 0

    rows = [{'student': student, 'completion': completion_map.get(student.id)} for student in students]
    return render(request, 'open_learning/activity_results_report.html', {
        'activity': activity,
        'lesson': lesson,
        'rows': rows,
        'total_students': len(students),
        'completed_students': completed_count,
        'not_completed_students': max(0, len(students) - completed_count),
        'completion_percent': completion_percent,
    })
