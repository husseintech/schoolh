from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import connection
from django.db.models import Avg, Count, Max, Min, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from openpyxl import Workbook

from school.models import Profile, Student

from .models import LearningLesson, LearningResourceLibrary
from .learning_models import (
    LessonAssignment, LessonQuiz, QuizAnswer, QuizAttempt, QuizQuestion,
)
from .enhancement_models import (
    GuardianStudentLink, LearningAchievement, LearningResourceFavorite,
    LearningResourceRating, RemediationPlan,
)
from .learning_views import learning_suite_ready
from .services.learning_events import enhancements_ready, notify_lesson_students
from .services.smart_assessment import generate_assignment_draft, generate_quiz_draft
from .views import _can_manage, _is_admin, _role, _teacher_of


def _student(request):
    try:
        return request.user.student_profile
    except Exception:
        return None


def _enhancement_guard(request):
    if not learning_suite_ready() or not enhancements_ready():
        messages.warning(request, 'الإضافات التعليمية الجديدة لم تُفعّل بعد على قاعدة البيانات.')
        return False
    return True


@login_required
@require_POST
def smart_quiz_generate(request, lesson_id):
    lesson = get_object_or_404(LearningLesson.objects.select_related('subject', 'teacher'), pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية لإدارة هذا الدرس')
        return redirect('open_learning_list')
    if not learning_suite_ready():
        messages.warning(request, 'جداول الاختبارات غير مفعلة بعد')
        return redirect('ol_lesson_builder', lesson_id=lesson.id)

    try:
        count = max(3, min(int(request.POST.get('question_count') or 5), 20))
    except ValueError:
        count = 5
    difficulty = request.POST.get('difficulty', 'medium')
    if difficulty not in {'easy', 'medium', 'hard'}:
        difficulty = 'medium'

    draft = generate_quiz_draft(lesson, count=count, difficulty=difficulty)
    quiz = LessonQuiz.objects.create(
        lesson=lesson,
        title=draft['title'],
        instructions=draft['instructions'],
        passing_score=draft['passing_score'],
        max_attempts=draft['max_attempts'],
        is_published=False,
    )
    QuizQuestion.objects.bulk_create([
        QuizQuestion(
            quiz=quiz,
            text=item['text'],
            question_type=item['question_type'],
            options=item['options'],
            correct_answer=item['correct_answer'],
            points=item.get('points', 1),
            order=index,
        )
        for index, item in enumerate(draft['questions'], start=1)
    ])
    messages.success(request, f'تم إنشاء اختبار ذكي من {count} أسئلة كمسودة. راجعه ثم انشره.')
    return redirect('ol_lesson_builder', lesson_id=lesson.id)


@login_required
@require_POST
def smart_assignment_generate(request, lesson_id):
    lesson = get_object_or_404(LearningLesson.objects.select_related('subject', 'teacher'), pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية لإدارة هذا الدرس')
        return redirect('open_learning_list')
    if not learning_suite_ready():
        messages.warning(request, 'جداول الواجبات غير مفعلة بعد')
        return redirect('ol_lesson_builder', lesson_id=lesson.id)

    difficulty = request.POST.get('difficulty', 'medium')
    if difficulty not in {'easy', 'medium', 'hard'}:
        difficulty = 'medium'
    draft = generate_assignment_draft(lesson, difficulty=difficulty)
    LessonAssignment.objects.create(
        lesson=lesson,
        title=draft['title'],
        instructions=draft['instructions'],
        points=draft['points'],
        is_published=False,
    )
    messages.success(request, 'تم إنشاء واجب ذكي كمسودة. راجعه ثم انشره للطلاب.')
    return redirect('ol_lesson_builder', lesson_id=lesson.id)


@login_required
@require_POST
def delete_question(request, question_id):
    question = get_object_or_404(QuizQuestion.objects.select_related('quiz__lesson'), pk=question_id)
    if not _can_manage(request, question.quiz.lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    lesson_id = question.quiz.lesson_id
    question.delete()
    messages.success(request, 'تم حذف السؤال')
    return redirect('ol_lesson_builder', lesson_id=lesson_id)


@login_required
@require_POST
def delete_quiz(request, quiz_id):
    quiz = get_object_or_404(LessonQuiz.objects.select_related('lesson'), pk=quiz_id)
    if not _can_manage(request, quiz.lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    lesson_id = quiz.lesson_id
    quiz.delete()
    messages.success(request, 'تم حذف الاختبار')
    return redirect('ol_lesson_builder', lesson_id=lesson_id)


@login_required
@require_POST
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(LessonAssignment.objects.select_related('lesson'), pk=assignment_id)
    if not _can_manage(request, assignment.lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    lesson_id = assignment.lesson_id
    assignment.delete()
    messages.success(request, 'تم حذف الواجب')
    return redirect('ol_lesson_builder', lesson_id=lesson_id)


@login_required
def quiz_analysis(request, quiz_id):
    quiz = get_object_or_404(
        LessonQuiz.objects.select_related('lesson', 'lesson__subject', 'lesson__teacher').prefetch_related('questions'),
        pk=quiz_id,
    )
    lesson = quiz.lesson
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية لعرض تحليل هذا الاختبار')
        return redirect('open_learning_list')

    class_ids = list(lesson.student_classes.values_list('id', flat=True))
    students = list(Student.objects.filter(student_class_id__in=class_ids).select_related('student_class'))
    attempts = QuizAttempt.objects.filter(quiz=quiz, student_id__in=[s.id for s in students])
    answers = QuizAnswer.objects.filter(attempt__quiz=quiz, attempt__student_id__in=[s.id for s in students])

    question_rows = []
    for question in quiz.questions.all():
        q_answers = answers.filter(question=question)
        total = q_answers.count()
        correct = q_answers.filter(is_correct=True).count()
        question_rows.append({
            'question': question,
            'total': total,
            'correct': correct,
            'incorrect': max(0, total - correct),
            'correct_percent': round(correct * 100 / total, 1) if total else 0,
        })
    question_rows.sort(key=lambda row: row['correct_percent'])

    risk_rows = []
    for student in students:
        student_attempts = list(attempts.filter(student=student).order_by('-percentage'))
        best = student_attempts[0] if student_attempts else None
        if not best or best.percentage < quiz.passing_score:
            risk_rows.append({'student': student, 'best': best})

    stats = attempts.aggregate(avg=Avg('percentage'), high=Max('percentage'), low=Min('percentage'))
    attempted = attempts.values('student_id').distinct().count()
    passed = attempts.filter(passed=True).values('student_id').distinct().count()
    return render(request, 'open_learning/quiz_analysis.html', {
        'quiz': quiz,
        'lesson': lesson,
        'question_rows': question_rows,
        'risk_rows': risk_rows,
        'total_students': len(students),
        'attempted': attempted,
        'passed': passed,
        'pass_rate': round(passed * 100 / attempted, 1) if attempted else 0,
        'average': stats['avg'],
        'highest': stats['high'],
        'lowest': stats['low'],
    })


@login_required
def quiz_attempt_detail(request, attempt_id):
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related('quiz__lesson', 'student', 'student__student_class').prefetch_related('answers__question'),
        pk=attempt_id,
    )
    if not _can_manage(request, attempt.quiz.lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    return render(request, 'open_learning/quiz_attempt_detail.html', {'attempt': attempt, 'lesson': attempt.quiz.lesson})


@login_required
def quiz_results_xlsx(request, quiz_id):
    quiz = get_object_or_404(LessonQuiz.objects.select_related('lesson'), pk=quiz_id)
    if not _can_manage(request, quiz.lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')

    class_ids = list(quiz.lesson.student_classes.values_list('id', flat=True))
    students = Student.objects.filter(student_class_id__in=class_ids).select_related('student_class').order_by('student_class__name', 'full_name')
    wb = Workbook()
    ws = wb.active
    ws.title = 'نتائج الاختبار'
    ws.append(['اسم الطالب', 'الصف', 'أفضل علامة', 'العلامة الكاملة', 'النسبة', 'الحالة', 'عدد المحاولات'])
    for student in students:
        attempts = QuizAttempt.objects.filter(quiz=quiz, student=student).order_by('-percentage')
        best = attempts.first()
        ws.append([
            student.full_name,
            student.student_class.name if student.student_class else '',
            float(best.score) if best else '',
            float(best.max_score) if best else '',
            float(best.percentage) if best else '',
            'ناجح' if best and best.passed else ('لم يجتز' if best else 'لم يتقدم'),
            attempts.count(),
        ])
    output = BytesIO()
    wb.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="quiz-{quiz.id}-results.xlsx"'
    return response


@login_required
def my_achievements(request):
    student = _student(request)
    if not student or not _enhancement_guard(request):
        return redirect('open_learning_list')
    achievements = LearningAchievement.objects.filter(student=student).select_related('lesson')
    remediation = RemediationPlan.objects.filter(student=student, status='active').select_related('lesson', 'quiz')
    favorites = LearningResourceFavorite.objects.filter(student=student).select_related('resource')
    return render(request, 'open_learning/my_achievements.html', {
        'student': student,
        'achievements': achievements,
        'remediation': remediation,
        'favorites': favorites,
    })


@login_required
@require_POST
def toggle_favorite(request, resource_id):
    student = _student(request)
    if not student or not _enhancement_guard(request):
        return redirect('open_learning_list')
    resource = get_object_or_404(LearningResourceLibrary, pk=resource_id, status='approved')
    favorite = LearningResourceFavorite.objects.filter(student=student, resource=resource).first()
    if favorite:
        favorite.delete()
        messages.success(request, 'تمت إزالة المصدر من المفضلة')
    else:
        LearningResourceFavorite.objects.create(student=student, resource=resource)
        messages.success(request, 'تمت إضافة المصدر إلى المفضلة')
    return redirect(request.POST.get('next') or 'ol_student_progress')


@login_required
@require_POST
def rate_resource(request, resource_id):
    student = _student(request)
    if not student or not _enhancement_guard(request):
        return redirect('open_learning_list')
    resource = get_object_or_404(LearningResourceLibrary, pk=resource_id, status='approved')
    try:
        rating = max(1, min(int(request.POST.get('rating') or 5), 5))
    except ValueError:
        rating = 5
    LearningResourceRating.objects.update_or_create(
        student=student,
        resource=resource,
        defaults={'rating': rating, 'note': request.POST.get('note', '').strip()[:300]},
    )
    messages.success(request, 'تم حفظ تقييم المصدر')
    return redirect(request.POST.get('next') or 'ol_student_progress')


@login_required
def guardian_portal(request):
    if not _enhancement_guard(request):
        return redirect('open_learning_list')
    links = GuardianStudentLink.objects.filter(guardian=request.user, is_active=True).select_related('student', 'student__student_class')
    if not links.exists():
        messages.error(request, 'لا يوجد طلاب مرتبطون بهذا الحساب كولي أمر')
        return redirect('open_learning_list')

    child_rows = []
    for link in links:
        student = link.student
        progress = student.open_learning_progress.select_related('lesson').all() if hasattr(student, 'open_learning_progress') else []
        attempts = QuizAttempt.objects.filter(student=student)
        submissions = student.open_learning_assignment_submissions.all()
        child_rows.append({
            'link': link,
            'student': student,
            'started': progress.exclude(status='not_started').count() if hasattr(progress, 'exclude') else 0,
            'completed': progress.filter(status='completed').count() if hasattr(progress, 'filter') else 0,
            'quiz_avg': attempts.aggregate(v=Avg('percentage'))['v'],
            'quiz_attempts': attempts.count(),
            'submissions': submissions.count(),
            'active_remediation': RemediationPlan.objects.filter(student=student, status='active').count(),
            'achievements': LearningAchievement.objects.filter(student=student).count(),
        })
    return render(request, 'open_learning/guardian_portal.html', {'child_rows': child_rows})


@login_required
def guardian_student_detail(request, student_id):
    if not _enhancement_guard(request):
        return redirect('open_learning_list')
    link = get_object_or_404(
        GuardianStudentLink.objects.select_related('student', 'student__student_class'),
        guardian=request.user, student_id=student_id, is_active=True,
    )
    student = link.student
    attempts = QuizAttempt.objects.filter(student=student).select_related('quiz', 'quiz__lesson').order_by('-submitted_at')[:30]
    submissions = student.open_learning_assignment_submissions.select_related('assignment', 'assignment__lesson').order_by('-submitted_at')[:30]
    remediation = RemediationPlan.objects.filter(student=student, status='active').select_related('lesson', 'quiz')
    achievements = LearningAchievement.objects.filter(student=student).select_related('lesson')
    return render(request, 'open_learning/guardian_student_detail.html', {
        'link': link, 'student': student, 'attempts': attempts, 'submissions': submissions,
        'remediation': remediation, 'achievements': achievements,
    })


@login_required
def guardian_manage(request):
    if not _is_admin(request):
        messages.error(request, 'هذه الصفحة لمدير النظام فقط')
        return redirect('open_learning_list')
    if not _enhancement_guard(request):
        return redirect('open_learning_list')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        student_id = request.POST.get('student_id')
        relation = request.POST.get('relation', '').strip() or 'ولي أمر'
        student = get_object_or_404(Student, pk=student_id)
        if not username:
            messages.error(request, 'اكتب اسم مستخدم ولي الأمر')
        else:
            guardian = User.objects.filter(username=username).first()
            if not guardian:
                if not password:
                    messages.error(request, 'اكتب كلمة مرور للحساب الجديد')
                    return redirect('ol_guardian_manage')
                guardian = User.objects.create_user(username=username, password=password)
                Profile.objects.create(user=guardian, role='guardian')
            GuardianStudentLink.objects.update_or_create(
                guardian=guardian, student=student,
                defaults={'relation': relation, 'is_active': True},
            )
            messages.success(request, f'تم ربط {guardian.username} بالطالب {student.full_name}')
            return redirect('ol_guardian_manage')

    links = GuardianStudentLink.objects.select_related('guardian', 'student', 'student__student_class').order_by('-created_at')
    students = Student.objects.select_related('student_class').order_by('student_class__name', 'full_name')
    return render(request, 'open_learning/guardian_manage.html', {'links': links, 'students': students})


@login_required
@require_POST
def guardian_unlink(request, link_id):
    if not _is_admin(request):
        messages.error(request, 'هذه العملية للمدير فقط')
        return redirect('open_learning_list')
    link = get_object_or_404(GuardianStudentLink, pk=link_id)
    link.is_active = False
    link.save(update_fields=['is_active'])
    messages.success(request, 'تم إيقاف ربط ولي الأمر بهذا الطالب')
    return redirect('ol_guardian_manage')


@login_required
def advanced_dashboard(request):
    role = _role(request)
    if role == 'teacher':
        teacher = _teacher_of(request.user)
        lessons = LearningLesson.objects.filter(teacher=teacher)
    elif _is_admin(request):
        lessons = LearningLesson.objects.all()
    else:
        messages.error(request, 'هذه اللوحة للمعلمين والإدارة')
        return redirect('open_learning_list')

    lesson_ids = list(lessons.values_list('id', flat=True))
    attempts = QuizAttempt.objects.filter(quiz__lesson_id__in=lesson_ids)
    quiz_ids = list(LessonQuiz.objects.filter(lesson_id__in=lesson_ids).values_list('id', flat=True))
    student_best = {}
    for attempt in attempts.order_by('student_id', 'quiz_id', '-percentage'):
        student_best.setdefault((attempt.student_id, attempt.quiz_id), attempt)
    at_risk_keys = [key for key, attempt in student_best.items() if not attempt.passed]
    at_risk_student_ids = sorted({student_id for student_id, _ in at_risk_keys})
    at_risk_students = Student.objects.filter(id__in=at_risk_student_ids).select_related('student_class')[:50]

    question_stats = []
    answers = QuizAnswer.objects.filter(attempt__quiz_id__in=quiz_ids)
    for question in QuizQuestion.objects.filter(quiz_id__in=quiz_ids).select_related('quiz', 'quiz__lesson'):
        q = answers.filter(question=question)
        total = q.count()
        if total:
            correct = q.filter(is_correct=True).count()
            question_stats.append({
                'question': question,
                'correct_percent': round(correct * 100 / total, 1),
                'total': total,
            })
    question_stats.sort(key=lambda row: row['correct_percent'])

    return render(request, 'open_learning/advanced_dashboard.html', {
        'lessons_count': lessons.count(),
        'quiz_attempts': attempts.count(),
        'average': attempts.aggregate(v=Avg('percentage'))['v'],
        'at_risk_students': at_risk_students,
        'at_risk_count': len(at_risk_student_ids),
        'hardest_questions': question_stats[:10],
        'active_remediation': RemediationPlan.objects.filter(lesson_id__in=lesson_ids, status='active').count() if enhancements_ready() else 0,
    })
