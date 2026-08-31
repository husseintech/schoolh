from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from school.models import Notification

from .models import LearningLesson
from .progress_models import StudentLessonProgress
from .learning_models import (
    LessonActivity, StudentActivityCompletion, LessonQuiz, QuizQuestion,
    QuizAttempt, QuizAnswer, LessonAssignment, AssignmentSubmission,
)
from .services.learning_events import (
    award_achievement, enhancements_ready, notify_lesson_students, update_remediation,
)
from .views import _can_manage, _is_admin, _role, _teacher_of


SUITE_TABLES = [
    StudentLessonProgress, LessonActivity, StudentActivityCompletion, LessonQuiz,
    QuizQuestion, QuizAttempt, QuizAnswer, LessonAssignment, AssignmentSubmission,
]


def learning_suite_ready():
    try:
        names = set(connection.introspection.table_names())
        return all(model._meta.db_table in names for model in SUITE_TABLES)
    except Exception:
        return False


def _student(request):
    try:
        return request.user.student_profile
    except Exception:
        return None


def _student_lesson(student, lesson_id):
    return get_object_or_404(
        LearningLesson.objects.select_related('subject', 'teacher').prefetch_related(
            'student_classes', 'resources', 'resources__library'
        ),
        pk=lesson_id, status='published', student_classes=student.student_class,
    )


def _safe_redirect_not_ready(request):
    messages.warning(request, 'حزمة التعلم الجديدة جاهزة في الكود، لكنها لم تُفعّل بعد على قاعدة البيانات.')
    return redirect('open_learning_list')


@login_required
def student_learning_path(request, lesson_id):
    student = _student(request)
    if not student:
        messages.error(request, 'هذه الصفحة مخصصة للطلاب')
        return redirect('open_learning_list')
    lesson = _student_lesson(student, lesson_id)
    if not learning_suite_ready():
        return render(request, 'open_learning/student_learning_path.html', {
            'lesson': lesson, 'student': student, 'suite_ready': False,
        })

    progress, _ = StudentLessonProgress.objects.get_or_create(student=student, lesson=lesson)
    progress.mark_started()
    activities = list(lesson.learning_activities.all())
    completed_ids = set(
        StudentActivityCompletion.objects.filter(student=student, activity__lesson=lesson)
        .values_list('activity_id', flat=True)
    )
    for activity in activities:
        activity.student_completed = activity.id in completed_ids

    quizzes = list(lesson.learning_quizzes.filter(is_published=True).prefetch_related('questions'))
    for quiz in quizzes:
        attempts = QuizAttempt.objects.filter(student=student, quiz=quiz)
        quiz.attempt_count = attempts.count()
        quiz.best_attempt = attempts.order_by('-percentage').first()
        quiz.can_attempt = quiz.attempt_count < quiz.max_attempts

    assignments = list(lesson.learning_assignments.filter(is_published=True))
    submission_map = {
        s.assignment_id: s for s in AssignmentSubmission.objects.filter(student=student, assignment__lesson=lesson)
    }
    for assignment in assignments:
        assignment.student_submission = submission_map.get(assignment.id)

    required = [a for a in activities if a.is_required]
    required_done = all(a.student_completed for a in required) if required else True
    quizzes_done = all(q.best_attempt and q.best_attempt.passed for q in quizzes) if quizzes else True
    assignments_done = all(a.student_submission for a in assignments) if assignments else True
    can_complete = required_done and quizzes_done and assignments_done

    remediation = []
    achievements = []
    favorite_ids = set()
    if enhancements_ready():
        from .enhancement_models import LearningAchievement, LearningResourceFavorite, RemediationPlan
        remediation = RemediationPlan.objects.filter(
            student=student, lesson=lesson, status='active'
        ).select_related('quiz')
        achievements = LearningAchievement.objects.filter(student=student, lesson=lesson)
        favorite_ids = set(
            LearningResourceFavorite.objects.filter(student=student).values_list('resource_id', flat=True)
        )

    resources = [r for r in lesson.resources.all() if r.status == 'approved' and r.library_id]
    for resource in resources:
        resource.is_favorite = resource.library_id in favorite_ids

    return render(request, 'open_learning/student_learning_path.html', {
        'lesson': lesson, 'student': student, 'suite_ready': True,
        'progress': progress, 'activities': activities, 'quizzes': quizzes,
        'assignments': assignments, 'can_complete': can_complete,
        'remediation': remediation, 'achievements': achievements, 'resources': resources,
        'enhancements_ready': enhancements_ready(),
    })


@login_required
@require_POST
def activity_complete(request, activity_id):
    student = _student(request)
    if not student or not learning_suite_ready():
        return _safe_redirect_not_ready(request)
    activity = get_object_or_404(LessonActivity.objects.select_related('lesson'), pk=activity_id)
    _student_lesson(student, activity.lesson_id)
    StudentActivityCompletion.objects.get_or_create(student=student, activity=activity)
    progress, _ = StudentLessonProgress.objects.get_or_create(student=student, lesson=activity.lesson)
    progress.mark_started()
    messages.success(request, 'تم تسجيل النشاط كمكتمل')
    return redirect('ol_student_learning_path', lesson_id=activity.lesson_id)


@login_required
def quiz_take(request, quiz_id):
    student = _student(request)
    if not student or not learning_suite_ready():
        return _safe_redirect_not_ready(request)
    quiz = get_object_or_404(
        LessonQuiz.objects.select_related('lesson').prefetch_related('questions'),
        pk=quiz_id, is_published=True,
    )
    _student_lesson(student, quiz.lesson_id)
    attempts_count = QuizAttempt.objects.filter(student=student, quiz=quiz).count()
    if attempts_count >= quiz.max_attempts:
        messages.warning(request, 'لقد استنفدت عدد المحاولات المسموح بها لهذا الاختبار')
        return redirect('ol_student_learning_path', lesson_id=quiz.lesson_id)

    if request.method == 'POST':
        questions = list(quiz.questions.all())
        max_score = sum(q.points for q in questions)
        with transaction.atomic():
            attempt = QuizAttempt.objects.create(student=student, quiz=quiz, max_score=max_score)
            score = Decimal('0')
            for question in questions:
                answer = (request.POST.get(f'q_{question.id}') or '').strip()
                correct = answer == question.correct_answer.strip()
                awarded = Decimal(str(question.points if correct else 0))
                score += awarded
                QuizAnswer.objects.create(
                    attempt=attempt, question=question, answer=answer,
                    is_correct=correct, awarded_points=awarded,
                )
            percentage = (score * Decimal('100') / Decimal(str(max_score))) if max_score else Decimal('0')
            attempt.score = score
            attempt.percentage = percentage.quantize(Decimal('0.01'))
            attempt.passed = attempt.percentage >= Decimal(str(quiz.passing_score))
            attempt.save(update_fields=['score', 'percentage', 'passed'])
            progress, _ = StudentLessonProgress.objects.get_or_create(student=student, lesson=quiz.lesson)
            progress.mark_started()

        update_remediation(student, quiz.lesson, quiz, attempt.percentage, attempt.passed)
        if attempt.percentage == Decimal('100.00'):
            award_achievement(
                student, quiz.lesson, 'perfect_quiz',
                f'علامة كاملة في {quiz.title}',
                'أحرز الطالب العلامة الكاملة في الاختبار.',
            )
        messages.success(request, f'تم تصحيح الاختبار تلقائياً. النتيجة: {attempt.percentage}%')
        return redirect('ol_student_learning_path', lesson_id=quiz.lesson_id)

    return render(request, 'open_learning/quiz_take.html', {'quiz': quiz, 'attempt_number': attempts_count + 1})


@login_required
def assignment_submit(request, assignment_id):
    student = _student(request)
    if not student or not learning_suite_ready():
        return _safe_redirect_not_ready(request)
    assignment = get_object_or_404(
        LessonAssignment.objects.select_related('lesson'), pk=assignment_id, is_published=True
    )
    _student_lesson(student, assignment.lesson_id)
    submission = AssignmentSubmission.objects.filter(student=student, assignment=assignment).first()
    if request.method == 'POST':
        answer_text = request.POST.get('answer_text', '').strip()
        answer_link = request.POST.get('answer_link', '').strip()
        if not answer_text and not answer_link:
            messages.error(request, 'اكتب إجابتك أو أضف رابطاً للتسليم')
        else:
            submission, _ = AssignmentSubmission.objects.update_or_create(
                student=student, assignment=assignment,
                defaults={
                    'answer_text': answer_text, 'answer_link': answer_link,
                    'status': 'submitted', 'grade': None, 'feedback': '',
                },
            )
            progress, _ = StudentLessonProgress.objects.get_or_create(student=student, lesson=assignment.lesson)
            progress.mark_started()
            messages.success(request, 'تم تسليم الواجب بنجاح')
            return redirect('ol_student_learning_path', lesson_id=assignment.lesson_id)
    return render(request, 'open_learning/assignment_submit.html', {'assignment': assignment, 'submission': submission})


@login_required
@require_POST
def complete_learning_path(request, lesson_id):
    student = _student(request)
    if not student or not learning_suite_ready():
        return _safe_redirect_not_ready(request)
    lesson = _student_lesson(student, lesson_id)
    required_ids = set(lesson.learning_activities.filter(is_required=True).values_list('id', flat=True))
    completed_ids = set(
        StudentActivityCompletion.objects.filter(student=student, activity_id__in=required_ids)
        .values_list('activity_id', flat=True)
    )
    if required_ids - completed_ids:
        messages.warning(request, 'أكمل الأنشطة الإلزامية أولاً')
        return redirect('ol_student_learning_path', lesson_id=lesson.id)
    for quiz in lesson.learning_quizzes.filter(is_published=True):
        if not QuizAttempt.objects.filter(student=student, quiz=quiz, passed=True).exists():
            messages.warning(request, 'يجب اجتياز الاختبارات المنشورة أولاً')
            return redirect('ol_student_learning_path', lesson_id=lesson.id)
    for assignment in lesson.learning_assignments.filter(is_published=True):
        if not AssignmentSubmission.objects.filter(student=student, assignment=assignment).exists():
            messages.warning(request, 'يجب تسليم الواجبات المنشورة أولاً')
            return redirect('ol_student_learning_path', lesson_id=lesson.id)
    progress, _ = StudentLessonProgress.objects.get_or_create(student=student, lesson=lesson)
    progress.mark_completed()
    award_achievement(
        student, lesson, 'lesson_complete', f'أكمل درس {lesson.title}',
        'أكمل الطالب الأنشطة والاختبارات والواجبات المطلوبة في مسار الدرس.',
    )
    messages.success(request, 'أحسنت، أتممت مسار الدرس بنجاح وحصلت على إنجاز جديد')
    return redirect('ol_my_achievements') if enhancements_ready() else redirect('open_learning_list')


@login_required
def lesson_builder(request, lesson_id):
    lesson = get_object_or_404(LearningLesson.objects.select_related('teacher', 'subject'), pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية لإدارة محتوى هذا الدرس')
        return redirect('open_learning_list')
    if not learning_suite_ready():
        return render(request, 'open_learning/lesson_builder.html', {'lesson': lesson, 'suite_ready': False})

    learning_link = f'/open-learning/learn/{lesson.id}/'
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_activity':
            title = request.POST.get('title', '').strip()
            instructions = request.POST.get('instructions', '').strip()
            if title and instructions:
                LessonActivity.objects.create(
                    lesson=lesson, title=title, instructions=instructions,
                    activity_type=request.POST.get('activity_type', 'practice'),
                    is_required=request.POST.get('is_required') == 'on',
                    order=request.POST.get('order') or 0,
                )
                if lesson.status == 'published':
                    notify_lesson_students(
                        lesson, f'نشاط جديد: {title}',
                        f'تمت إضافة نشاط جديد إلى درس {lesson.title}.', learning_link,
                    )
                messages.success(request, 'تمت إضافة النشاط')
        elif action == 'add_quiz':
            title = request.POST.get('title', '').strip()
            if title:
                published = request.POST.get('is_published') == 'on'
                LessonQuiz.objects.create(
                    lesson=lesson, title=title, instructions=request.POST.get('instructions', '').strip(),
                    passing_score=max(0, min(100, int(request.POST.get('passing_score') or 50))),
                    max_attempts=max(1, int(request.POST.get('max_attempts') or 2)),
                    is_published=published,
                )
                if published:
                    notify_lesson_students(
                        lesson, f'اختبار جديد: {title}',
                        f'تم نشر اختبار جديد في درس {lesson.title}.', learning_link,
                    )
                messages.success(request, 'تم إنشاء الاختبار')
        elif action == 'add_question':
            quiz = get_object_or_404(LessonQuiz, pk=request.POST.get('quiz_id'), lesson=lesson)
            text = request.POST.get('text', '').strip()
            correct_answer = request.POST.get('correct_answer', '').strip()
            qtype = request.POST.get('question_type', 'mcq')
            options = [x.strip() for x in request.POST.get('options', '').split('\n') if x.strip()]
            if qtype == 'true_false':
                options = ['صح', 'خطأ']
            if text and correct_answer:
                QuizQuestion.objects.create(
                    quiz=quiz, text=text, question_type=qtype, options=options,
                    correct_answer=correct_answer, points=max(1, int(request.POST.get('points') or 1)),
                    order=request.POST.get('order') or 0,
                )
                messages.success(request, 'تمت إضافة السؤال')
        elif action == 'toggle_quiz':
            quiz = get_object_or_404(LessonQuiz, pk=request.POST.get('quiz_id'), lesson=lesson)
            quiz.is_published = not quiz.is_published
            quiz.save(update_fields=['is_published'])
            if quiz.is_published:
                notify_lesson_students(
                    lesson, f'اختبار متاح: {quiz.title}',
                    f'أصبح الاختبار متاحاً في درس {lesson.title}.', learning_link,
                )
        elif action == 'add_assignment':
            title = request.POST.get('title', '').strip()
            instructions = request.POST.get('instructions', '').strip()
            due_raw = request.POST.get('due_at', '').strip()
            due_at = None
            if due_raw:
                try:
                    due_at = timezone.datetime.fromisoformat(due_raw)
                    if timezone.is_naive(due_at):
                        due_at = timezone.make_aware(due_at)
                except ValueError:
                    due_at = None
            if title and instructions:
                published = request.POST.get('is_published') == 'on'
                LessonAssignment.objects.create(
                    lesson=lesson, title=title, instructions=instructions,
                    due_at=due_at, points=max(1, int(request.POST.get('points') or 10)),
                    is_published=published,
                )
                if published:
                    notify_lesson_students(
                        lesson, f'واجب جديد: {title}',
                        f'تم نشر واجب جديد في درس {lesson.title}.', learning_link,
                    )
                messages.success(request, 'تمت إضافة الواجب')
        elif action == 'toggle_assignment':
            assignment = get_object_or_404(
                LessonAssignment, pk=request.POST.get('assignment_id'), lesson=lesson
            )
            assignment.is_published = not assignment.is_published
            assignment.save(update_fields=['is_published'])
            if assignment.is_published:
                notify_lesson_students(
                    lesson, f'واجب متاح: {assignment.title}',
                    f'أصبح الواجب متاحاً في درس {lesson.title}.', learning_link,
                )
        return redirect('ol_lesson_builder', lesson_id=lesson.id)

    quizzes = lesson.learning_quizzes.prefetch_related('questions').all()
    return render(request, 'open_learning/lesson_builder.html', {
        'lesson': lesson, 'suite_ready': True, 'activities': lesson.learning_activities.all(),
        'quizzes': quizzes, 'assignments': lesson.learning_assignments.all(),
    })


@login_required
def teacher_learning_dashboard(request):
    if not learning_suite_ready():
        return render(request, 'open_learning/teacher_learning_dashboard.html', {'suite_ready': False})
    role = _role(request)
    if role == 'teacher':
        teacher = _teacher_of(request.user)
        lessons = LearningLesson.objects.filter(teacher=teacher)
    elif _is_admin(request):
        lessons = LearningLesson.objects.all()
    else:
        messages.error(request, 'هذه الصفحة للمعلمين والإدارة')
        return redirect('open_learning_list')

    lesson_ids = list(lessons.values_list('id', flat=True))
    progress_qs = StudentLessonProgress.objects.filter(lesson_id__in=lesson_ids)
    attempts = QuizAttempt.objects.filter(quiz__lesson_id__in=lesson_ids)
    submissions = AssignmentSubmission.objects.filter(assignment__lesson_id__in=lesson_ids)
    lesson_rows = []
    for lesson in lessons.select_related('subject', 'teacher').prefetch_related('student_classes'):
        p = progress_qs.filter(lesson=lesson)
        lesson_rows.append({
            'lesson': lesson,
            'started': p.exclude(status='not_started').count(),
            'completed': p.filter(status='completed').count(),
            'quiz_attempts': attempts.filter(quiz__lesson=lesson).count(),
            'avg_quiz': attempts.filter(quiz__lesson=lesson).aggregate(v=Avg('percentage'))['v'],
            'submissions': submissions.filter(assignment__lesson=lesson).count(),
        })
    return render(request, 'open_learning/teacher_learning_dashboard.html', {
        'suite_ready': True, 'lesson_rows': lesson_rows,
        'total_started': progress_qs.exclude(status='not_started').count(),
        'total_completed': progress_qs.filter(status='completed').count(),
        'total_attempts': attempts.count(), 'total_submissions': submissions.count(),
    })


@login_required
def assignment_review(request, submission_id):
    if not learning_suite_ready():
        return _safe_redirect_not_ready(request)
    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related('assignment__lesson', 'student', 'student__user'),
        pk=submission_id,
    )
    lesson = submission.assignment.lesson
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    if request.method == 'POST':
        grade_raw = request.POST.get('grade', '').strip()
        try:
            grade = Decimal(grade_raw)
        except Exception:
            grade = None
        if grade is not None:
            grade = max(Decimal('0'), min(grade, Decimal(str(submission.assignment.points))))
        submission.grade = grade
        submission.feedback = request.POST.get('feedback', '').strip()
        submission.status = 'reviewed'
        submission.save()
        Notification.objects.create(
            user=submission.student.user,
            title=f'تم تقييم الواجب: {submission.assignment.title}',
            message=(
                f'العلامة: {grade}/{submission.assignment.points}. '
                f'{submission.feedback}' if grade is not None else submission.feedback
            ),
            link=f'/open-learning/learn/{lesson.id}/',
        )
        messages.success(request, 'تم حفظ تقييم الواجب وإشعار الطالب')
        return redirect('ol_assignment_results_report', assignment_id=submission.assignment_id)
    return render(request, 'open_learning/assignment_review.html', {'submission': submission})
