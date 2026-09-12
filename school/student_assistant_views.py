import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from open_learning.services.ai_service import AIServiceUnavailable, get_provider

from .models import AuditLog, StudentAssistantKnowledge, StudentAssistantLog, StudentAssistantSettings
from .student_assistant import (
    MAX_QUESTION_LENGTH,
    ai_questions_today,
    answer_from_knowledge,
    answer_guided_question,
    assistant_settings,
    build_learning_context,
    cached_ai_answer,
    hourly_request_limit_reached,
    privacy_guard_answer,
    safe_internal_url,
)


def _student_only(request):
    return getattr(getattr(request.user, 'profile', None), 'role', None) == 'student'


def _record(student, question, result, *, success=True, tokens=None, duration=None):
    return StudentAssistantLog.objects.create(
        student=student,
        question=question,
        answer=(result.get('answer') or '')[:2500],
        mode=result.get('mode', 'guided'),
        success=success,
        estimated_tokens=tokens,
        duration_ms=duration,
    )


def _audit(user, action, details=''):
    try:
        AuditLog.objects.create(
            user=user,
            user_role=user.profile.role,
            action=action,
            details=details,
        )
    except Exception:
        pass


@login_required
@require_POST
def student_assistant_ask(request):
    if not _student_only(request):
        return JsonResponse({'error': 'هذه الخدمة مخصصة لحسابات الطلاب فقط.'}, status=403)
    student = getattr(request.user, 'student_profile', None)
    if not student:
        return JsonResponse({'error': 'لا يوجد ملف طالب مرتبط بهذا الحساب.'}, status=403)

    settings_obj = assistant_settings()
    if not settings_obj.enabled:
        return JsonResponse({'error': 'مساعد الطلاب متوقف مؤقتًا من إدارة المدرسة.'}, status=503)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': 'تعذر قراءة السؤال.'}, status=400)
    question = str(payload.get('question') or '').strip()
    if len(question) < 2:
        return JsonResponse({'error': 'اكتب سؤالًا واضحًا من كلمتين على الأقل.'}, status=400)
    if len(question) > MAX_QUESTION_LENGTH:
        return JsonResponse({'error': f'يجب ألا يزيد السؤال على {MAX_QUESTION_LENGTH} حرفًا.'}, status=400)
    privacy_result = privacy_guard_answer(question)
    if privacy_result:
        privacy_result.update(
            success=True,
            ai_remaining=max(0, settings_obj.daily_ai_limit - ai_questions_today(student)),
        )
        return JsonResponse(privacy_result)
    if hourly_request_limit_reached(student):
        return JsonResponse({'error': 'أرسلت عددًا كبيرًا من الأسئلة خلال ساعة. خذ استراحة قصيرة ثم حاول مجددًا.'}, status=429)

    result = answer_guided_question(student, question) or answer_from_knowledge(question)
    if result:
        _record(student, question, result)
        result.update(success=True, ai_remaining=max(0, settings_obj.daily_ai_limit - ai_questions_today(student)))
        return JsonResponse(result)

    if not settings_obj.educational_ai_enabled:
        result = {
            'answer': 'المساعدة التعليمية الذكية متوقفة حاليًا، لكنني ما زلت أستطيع مساعدتك في الوصول إلى خدمات الموقع.',
            'suggestions': ['ما المطلوب مني؟', 'أين أجد دروسي؟', 'كيف أفتح ملفي؟'],
            'mode': 'guided',
        }
        _record(student, question, result)
        return JsonResponse({**result, 'success': True, 'ai_remaining': 0})

    used_today = ai_questions_today(student)
    if used_today >= settings_obj.daily_ai_limit:
        return JsonResponse({
            'error': 'استخدمت الحد اليومي للأسئلة التعليمية الذكية. يمكنك الاستمرار باستخدام أسئلة الإرشاد إلى خدمات الموقع.',
            'ai_remaining': 0,
        }, status=429)

    cached = cached_ai_answer(student, question)
    if cached:
        result = {
            'answer': cached.answer,
            'suggestions': [],
            'mode': 'cache',
        }
        _record(student, question, result)
        return JsonResponse({**result, 'success': True, 'ai_remaining': settings_obj.daily_ai_limit - used_today})

    provider = get_provider()
    if not provider or not hasattr(provider, 'answer_student_question'):
        result = {
            'answer': 'المساعد التعليمي الذكي غير متاح مؤقتًا. يمكنك سؤال معلمك، أو استخدام أزرار المساعدة للوصول إلى دروسك وملفك.',
            'suggestions': ['أين أجد دروسي؟', 'ما المطلوب مني؟'],
            'mode': 'ai',
        }
        _record(student, question, result, success=False)
        return JsonResponse({**result, 'success': False, 'ai_remaining': max(0, settings_obj.daily_ai_limit - used_today - 1)}, status=503)

    context = build_learning_context(student, question)
    try:
        data, tokens, duration = provider.answer_student_question(
            question=question,
            grade=student.student_class.name if student.student_class else '',
            learning_context=context,
        )
        result = {
            'answer': data['answer'],
            'suggestions': data.get('suggestions', []),
            'mode': 'ai',
        }
        _record(student, question, result, tokens=tokens, duration=duration)
        return JsonResponse({
            **result,
            'success': True,
            'ai_remaining': max(0, settings_obj.daily_ai_limit - used_today - 1),
        })
    except AIServiceUnavailable as exc:
        result = {
            'answer': str(exc),
            'suggestions': ['أين أجد دروسي؟', 'ما المطلوب مني؟'],
            'mode': 'ai',
        }
        _record(student, question, result, success=False)
        return JsonResponse({
            **result,
            'success': False,
            'ai_remaining': max(0, settings_obj.daily_ai_limit - used_today - 1),
        }, status=503)


@login_required
def student_assistant_admin(request):
    if getattr(getattr(request.user, 'profile', None), 'role', None) != 'admin':
        messages.error(request, 'هذه الصفحة متاحة لمدير المدرسة فقط')
        return redirect('dashboard')

    settings_obj = StudentAssistantSettings.objects.order_by('pk').first()
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'save_settings':
            if settings_obj is None:
                settings_obj = StudentAssistantSettings()
            try:
                daily_limit = int(request.POST.get('daily_ai_limit', 10))
            except (TypeError, ValueError):
                daily_limit = 10
            settings_obj.enabled = 'enabled' in request.POST
            settings_obj.educational_ai_enabled = 'educational_ai_enabled' in request.POST
            settings_obj.daily_ai_limit = min(50, max(1, daily_limit))
            settings_obj.welcome_message = (
                request.POST.get('welcome_message', '').strip()[:500]
                or StudentAssistantSettings._meta.get_field('welcome_message').default
            )
            settings_obj.updated_by = request.user
            settings_obj.save()
            _audit(
                request.user,
                'تعديل إعدادات مساعد الطلاب',
                f'التشغيل: {settings_obj.enabled}، Gemini: {settings_obj.educational_ai_enabled}، الحد اليومي: {settings_obj.daily_ai_limit}',
            )
            messages.success(request, 'تم حفظ إعدادات مساعد الطلاب')
        elif action == 'add_knowledge':
            title = request.POST.get('title', '').strip()[:120]
            keywords = request.POST.get('keywords', '').strip()[:300]
            answer = request.POST.get('answer', '').strip()[:2000]
            action_url = safe_internal_url(request.POST.get('action_url', ''))
            action_label = request.POST.get('action_label', '').strip()[:80] if action_url else ''
            try:
                priority = min(100, max(0, int(request.POST.get('priority', 10))))
            except (TypeError, ValueError):
                priority = 10
            if not title or not keywords or not answer:
                messages.error(request, 'أدخل العنوان والكلمات المفتاحية والإجابة')
            elif request.POST.get('action_url', '').strip() and not action_url:
                messages.error(request, 'يجب أن يكون الرابط داخليًا ويبدأ بعلامة /')
            else:
                StudentAssistantKnowledge.objects.create(
                    title=title,
                    keywords=keywords,
                    answer=answer,
                    action_label=action_label,
                    action_url=action_url,
                    priority=priority,
                    created_by=request.user,
                )
                _audit(request.user, 'إضافة إجابة لمساعد الطلاب', title)
                messages.success(request, 'تمت إضافة الإجابة المعتمدة')
        elif action in ('toggle_knowledge', 'delete_knowledge'):
            item = get_object_or_404(StudentAssistantKnowledge, pk=request.POST.get('knowledge_id'))
            if action == 'toggle_knowledge':
                item.is_active = not item.is_active
                item.save(update_fields=['is_active', 'updated_at'])
                _audit(request.user, 'تغيير حالة إجابة مساعد الطلاب', f'{item.title}: {item.is_active}')
                messages.success(request, 'تم تحديث حالة الإجابة')
            else:
                item_title = item.title
                item.delete()
                _audit(request.user, 'حذف إجابة مساعد الطلاب', item_title)
                messages.success(request, 'تم حذف الإجابة المعتمدة')
        return redirect('student_assistant_admin')

    settings_obj = settings_obj or assistant_settings()
    logs = StudentAssistantLog.objects.select_related('student__student_class')
    today = timezone.localdate()
    today_logs = logs.filter(created_at__date=today)
    top_students = list(
        logs.filter(student__isnull=False)
        .values('student_id', 'student__full_name', 'student__student_class__name')
        .annotate(
            total=Count('id'),
            ai_count=Count('id', filter=Q(mode='ai')),
        )
        .order_by('-total', 'student__full_name')[:8]
    )
    paginator = Paginator(logs, 40)
    return render(request, 'school/student_assistant_admin.html', {
        'assistant_settings': settings_obj,
        'knowledge_items': StudentAssistantKnowledge.objects.all(),
        'logs_page': paginator.get_page(request.GET.get('page')),
        'stats': {
            'total': logs.count(),
            'today': today_logs.count(),
            'ai_today': today_logs.filter(mode='ai').count(),
            'students': logs.filter(student__isnull=False).values('student_id').distinct().count(),
            'failed': logs.filter(success=False).count(),
        },
        'top_students': top_students,
    })
