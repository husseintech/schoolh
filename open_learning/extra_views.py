from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from school.models import Student, has_perm

from .enhancement_models import GuardianStudentLink, LearningAchievement, RemediationPlan
from .learning_models import OpenResourceMetadata, QuizAttempt, AssignmentSubmission
from .models import LearningResourceLibrary
from .progress_models import StudentLessonProgress
from .services.learning_events import enhancements_ready
from .views import _is_admin, _role, _teacher_of


def _can_view_student(request, student):
    role = _role(request)
    if role == 'admin':
        return True
    if role == 'student':
        return getattr(request.user, 'student_profile', None) == student
    if role in {'vice_principal', 'secretary'}:
        return has_perm(request.user, 'students', 'view')
    if role == 'teacher':
        teacher = _teacher_of(request.user)
        return bool(
            teacher and has_perm(request.user, 'students', 'view')
            and teacher.classes.filter(pk=student.student_class_id).exists()
        )
    if role == 'guardian' and enhancements_ready():
        return GuardianStudentLink.objects.filter(
            guardian=request.user, student=student, is_active=True
        ).exists()
    return False


@login_required
def student_learning_record(request, student_id):
    student = get_object_or_404(Student.objects.select_related('student_class', 'user'), pk=student_id)
    if not _can_view_student(request, student):
        messages.error(request, 'ليس لديك صلاحية لعرض سجل تعلم هذا الطالب')
        return redirect('dashboard')

    progress = StudentLessonProgress.objects.filter(student=student).select_related('lesson', 'lesson__subject')
    attempts = QuizAttempt.objects.filter(student=student).select_related('quiz', 'quiz__lesson').order_by('-submitted_at')
    submissions = AssignmentSubmission.objects.filter(student=student).select_related(
        'assignment', 'assignment__lesson'
    ).order_by('-submitted_at')
    achievements = []
    remediation = []
    if enhancements_ready():
        achievements = LearningAchievement.objects.filter(student=student).select_related('lesson')
        remediation = RemediationPlan.objects.filter(student=student, status='active').select_related('lesson', 'quiz')

    return render(request, 'open_learning/student_learning_record.html', {
        'student': student,
        'progress': progress,
        'attempts': attempts[:30],
        'submissions': submissions[:30],
        'achievements': achievements,
        'remediation': remediation,
        'started_count': progress.exclude(status='not_started').count(),
        'completed_count': progress.filter(status='completed').count(),
        'quiz_count': attempts.count(),
        'quiz_average': attempts.aggregate(v=Avg('percentage'))['v'],
        'submission_count': submissions.count(),
    })


@login_required
def achievement_certificate(request, achievement_id):
    achievement = get_object_or_404(
        LearningAchievement.objects.select_related('student', 'student__student_class', 'lesson', 'lesson__subject'),
        pk=achievement_id,
    )
    if not _can_view_student(request, achievement.student):
        messages.error(request, 'ليس لديك صلاحية لعرض هذه الشهادة')
        return redirect('dashboard')
    return render(request, 'open_learning/achievement_certificate.html', {'achievement': achievement})


@login_required
def oer_metadata_manage(request):
    role = _role(request)
    if role == 'teacher':
        teacher = _teacher_of(request.user)
        resource_ids = LearningResourceLibrary.objects.filter(
            lesson_links__lesson__teacher=teacher
        ).values_list('id', flat=True).distinct()
        resources = LearningResourceLibrary.objects.filter(id__in=resource_ids)
    elif _is_admin(request):
        resources = LearningResourceLibrary.objects.all()
    else:
        messages.error(request, 'هذه الصفحة للمعلمين والإدارة')
        return redirect('open_learning_list')

    resources = resources.prefetch_related('ratings').order_by('title')
    if request.method == 'POST':
        resource = get_object_or_404(resources, pk=request.POST.get('resource_id'))
        license_type = request.POST.get('license_type', 'unknown')
        allowed = {key for key, _ in OpenResourceMetadata.LICENSE_CHOICES}
        if license_type not in allowed:
            license_type = 'unknown'
        verified = request.POST.get('verified_open_license') == 'on'
        OpenResourceMetadata.objects.update_or_create(
            library=resource,
            defaults={
                'license_type': license_type,
                'author': request.POST.get('author', '').strip()[:250],
                'attribution': request.POST.get('attribution', '').strip(),
                'source_url': request.POST.get('source_url', '').strip()[:700],
                'verified_open_license': verified,
                'verified_at': timezone.now() if verified else None,
            },
        )
        messages.success(request, f'تم حفظ بيانات ترخيص المصدر: {resource.title}')
        return redirect('ol_oer_metadata_manage')

    rows = []
    for resource in resources:
        try:
            metadata = resource.open_metadata
        except OpenResourceMetadata.DoesNotExist:
            metadata = None
        rows.append({
            'resource': resource,
            'metadata': metadata,
            'rating_average': resource.ratings.aggregate(v=Avg('rating'))['v'] if enhancements_ready() else None,
            'rating_count': resource.ratings.count() if enhancements_ready() else 0,
        })
    return render(request, 'open_learning/oer_metadata_manage.html', {
        'rows': rows,
        'licenses': OpenResourceMetadata.LICENSE_CHOICES,
    })
