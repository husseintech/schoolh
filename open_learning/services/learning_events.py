from django.db import connection

from school.models import Notification


def enhancements_ready():
    try:
        from open_learning.enhancement_models import LearningAchievement, RemediationPlan
        names = set(connection.introspection.table_names())
        return all(model._meta.db_table in names for model in [LearningAchievement, RemediationPlan])
    except Exception:
        return False


def notify_lesson_students(lesson, title, message, link=''):
    student_users = lesson.student_classes.values_list('students__user_id', flat=True).exclude(students__user_id=None).distinct()
    existing = set(
        Notification.objects.filter(user_id__in=student_users, title=title, link=link).values_list('user_id', flat=True)
    )
    notifications = [
        Notification(user_id=user_id, title=title, message=message, link=link)
        for user_id in student_users if user_id not in existing
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)


def award_achievement(student, lesson, kind, title, description=''):
    if not enhancements_ready():
        return None
    from open_learning.enhancement_models import LearningAchievement
    achievement, _ = LearningAchievement.objects.get_or_create(
        student=student,
        lesson=lesson,
        kind=kind,
        defaults={'title': title, 'description': description},
    )
    return achievement


def update_remediation(student, lesson, quiz, percentage, passed):
    if not enhancements_ready():
        return None
    from open_learning.enhancement_models import RemediationPlan
    from open_learning.services.smart_assessment import remediation_text

    if passed:
        RemediationPlan.objects.filter(student=student, quiz=quiz, status='active').update(status='completed')
        return None

    plan, _ = RemediationPlan.objects.update_or_create(
        student=student,
        quiz=quiz,
        defaults={
            'lesson': lesson,
            'reason': f'نتيجة أقل من نسبة النجاح ({percentage}%)',
            'recommendation': remediation_text(lesson, quiz, percentage),
            'status': 'active',
        },
    )
    return plan
