from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Max, Min
from django.shortcuts import get_object_or_404, redirect, render

from school.models import Student

from .learning_models import LessonQuiz, QuizAttempt
from .learning_views import learning_suite_ready
from .views import _can_manage


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

    class_ids = list(lesson.student_classes.values_list('id', flat=True))
    students = list(
        Student.objects.filter(student_class_id__in=class_ids)
        .select_related('student_class')
        .order_by('student_class__name', 'full_name')
    )

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
