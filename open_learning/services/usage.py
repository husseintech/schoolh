"""سجل استخدام الذكاء الاصطناعي + الحماية من الضغط المتكرر (Rate Limiting)."""
from datetime import timedelta

from django.utils import timezone

from open_learning.models import AIUsageLog

RATE_LIMIT_MINUTES = 3
CACHE_OPERATION = 'cache_hit'


def log_usage(user, lesson, operation, provider='', model='', success=True, error='', tokens=None, duration_ms=None):
    """يسجل عملية AI في AIUsageLog. الخطأ يُسجل نصياً عاماً بدون أي مفاتيح."""
    AIUsageLog.objects.create(
        user=user if user and user.is_authenticated else None,
        lesson=lesson,
        operation=operation,
        provider=provider,
        model=model,
        success=success,
        error=(error or '')[:2000],
        estimated_tokens=tokens,
        duration_ms=duration_ms,
    )


def recent_ai_operation(lesson_id, operation, minutes=RATE_LIMIT_MINUTES):
    """هل تم تنفيذ نفس العملية لنفس الدرس مؤخراً؟ (يمنع الضغط المتكرر)."""
    cutoff = timezone.now() - timedelta(minutes=minutes)
    return AIUsageLog.objects.filter(
        lesson_id=lesson_id, operation=operation, success=True, created_at__gte=cutoff,
    ).exists()
