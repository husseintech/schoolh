import json
import logging
import mimetypes
import re
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from open_learning.google_drive import GoogleDriveAuthError, GoogleDriveService
from open_learning.services.ai_service import AIServiceUnavailable, get_provider

from .curriculum_assistant import (
    MAX_QUESTION_LENGTH,
    CurriculumPackageError,
    build_source_fallback_answer,
    cached_answer,
    curriculum_settings,
    hourly_limit_reached,
    hydrate_citations,
    import_curriculum_package,
    is_grade_four,
    map_provider_citations,
    mark_cache_hit,
    questions_used_today,
    retrieve_curriculum_context,
    save_cached_answer,
)
from .models import (
    AuditLog,
    CurriculumAssistantSettings,
    CurriculumConversation,
    CurriculumLesson,
    CurriculumMessage,
    CurriculumPage,
    CurriculumSource,
)
from .student_assistant import privacy_guard_answer, student_short_name


MAX_SOURCE_PDF_SIZE = 100 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 2 * 1024 * 1024
UPLOAD_TOKEN_MAX_AGE = 60 * 60
UPLOAD_TOKEN_SALT = 'curriculum-source-drive-resumable-v1'
CURRICULUM_FOLDER = 'مصادر مساعد المنهاج'
logger = logging.getLogger(__name__)


def _role(request):
    return getattr(getattr(request.user, 'profile', None), 'role', None)


def _admin_only(request):
    return _role(request) == 'admin'


def _student(request):
    if _role(request) != 'student':
        return None
    return getattr(request.user, 'student_profile', None)


def _student_is_supported(student):
    return bool(student and student.student_class and is_grade_four(student.student_class.name))


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


def _error(message, status=400, code='request_error', **extra):
    payload = {'ok': False, 'error': message, 'code': code}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def _drive_error(exc):
    status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
    if isinstance(exc, GoogleDriveAuthError) or status_code in (401, 403):
        return _error(
            'انتهى اتصال Google Drive. أعد ربط الحساب من إعدادات التخزين.',
            status=409,
            code='drive_reconnect',
            reconnect_url=reverse('ol_storage_settings'),
        )
    if status_code in (404, 410):
        return _error('انتهت جلسة الرفع؛ أعد اختيار الملف.', status=409, code='upload_session_expired')
    return _error('تعذّر الوصول إلى Google Drive الآن. حاول مرة أخرى.', status=502, code='drive_unavailable')


@login_required
def curriculum_assistant_home(request):
    student = _student(request)
    if not student:
        if _admin_only(request):
            return redirect('curriculum_assistant_admin')
        messages.error(request, 'مساعد المنهاج متاح حاليًا لحسابات الطلاب فقط.')
        return redirect('dashboard')

    settings_obj = curriculum_settings()
    supported = _student_is_supported(student)
    sources = CurriculumSource.objects.none()
    if supported and settings_obj.enabled:
        sources = CurriculumSource.objects.filter(
            grade_level=4, status='published',
        ).prefetch_related('lessons').order_by('term', 'subject_name')
    source_id = request.GET.get('source')
    selected_source = next((row for row in sources if str(row.pk) == str(source_id)), None)
    if not selected_source:
        selected_source = next(iter(sources), None)
    lesson_id = request.GET.get('lesson')
    selected_lesson = None
    if selected_source:
        selected_lesson = next(
            (row for row in selected_source.lessons.all() if str(row.pk) == str(lesson_id)), None,
        )

    used = questions_used_today(student)
    conversations = CurriculumConversation.objects.filter(student=student).select_related(
        'source', 'lesson',
    )[:8]
    return render(request, 'school/curriculum_assistant.html', {
        'student': student,
        'student_name': student_short_name(student.full_name),
        'settings_obj': settings_obj,
        'supported': supported,
        'sources': sources,
        'selected_source': selected_source,
        'selected_lesson': selected_lesson,
        'initial_conversation_id': request.GET.get('conversation', ''),
        'questions_remaining': max(0, settings_obj.daily_question_limit - used),
        'conversations': conversations,
    })


@login_required
def curriculum_conversation(request, conversation_id):
    student = _student(request)
    if not _student_is_supported(student):
        return _error('هذه المحادثة غير متاحة لهذا الحساب.', status=403)
    conversation = get_object_or_404(
        CurriculumConversation.objects.select_related('source', 'lesson'),
        pk=conversation_id,
        student=student,
        source__status='published',
        source__grade_level=4,
    )
    return JsonResponse({
        'ok': True,
        'conversation': {
            'id': conversation.pk,
            'source_id': conversation.source_id,
            'lesson_id': conversation.lesson_id,
            'title': conversation.title,
            'messages': [
                {
                    'role': row.role,
                    'content': row.content,
                    'citations': hydrate_citations(row.citations) if row.role == 'assistant' else [],
                }
                for row in conversation.messages.all()
            ],
        },
    })


@login_required
@require_POST
def curriculum_assistant_ask(request):
    student = _student(request)
    if not student:
        return _error('هذه الخدمة مخصصة لحسابات الطلاب فقط.', status=403)
    if not _student_is_supported(student):
        return _error('النسخة الحالية من مساعد المنهاج مخصصة للصف الرابع.', status=403)
    settings_obj = curriculum_settings()
    if not settings_obj.enabled:
        return _error('مساعد المنهاج متوقف مؤقتًا من إدارة المدرسة.', status=503)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error('تعذر قراءة السؤال.')

    question = str(payload.get('question') or '').strip()
    if len(question) < 2:
        return _error('اكتب سؤالًا واضحًا من كلمتين على الأقل.')
    if len(question) > MAX_QUESTION_LENGTH:
        return _error(f'يجب ألا يزيد السؤال على {MAX_QUESTION_LENGTH} حرفًا.')
    privacy_result = privacy_guard_answer(question)
    if privacy_result:
        return JsonResponse({
            'ok': True,
            'answer': privacy_result['answer'],
            'citations': [],
            'suggestions': privacy_result.get('suggestions', []),
            'conversation_id': None,
            'remaining': max(0, settings_obj.daily_question_limit - questions_used_today(student)),
        })
    if hourly_limit_reached(student):
        return _error('أرسلت عددًا كبيرًا من الأسئلة خلال ساعة. خذ استراحة قصيرة ثم حاول.', status=429)

    used = questions_used_today(student)
    if used >= settings_obj.daily_question_limit:
        return _error('استخدمت الحد اليومي لأسئلة المنهاج.', status=429, remaining=0)
    source = get_object_or_404(
        CurriculumSource,
        pk=payload.get('source_id'),
        grade_level=4,
        status='published',
    )
    lesson = None
    if payload.get('lesson_id'):
        lesson = get_object_or_404(CurriculumLesson, pk=payload['lesson_id'], source=source)

    conversation = None
    if payload.get('conversation_id'):
        conversation = CurriculumConversation.objects.filter(
            pk=payload['conversation_id'], student=student, source=source, lesson=lesson,
        ).first()
    if not conversation:
        conversation = CurriculumConversation.objects.create(
            student=student,
            source=source,
            lesson=lesson,
            title=question[:157] + ('…' if len(question) > 157 else ''),
        )

    CurriculumMessage.objects.create(conversation=conversation, role='user', content=question)
    cache = cached_answer(source, lesson, question)
    if cache:
        citations = hydrate_citations(cache.citations)
        CurriculumMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=cache.answer,
            citations=cache.citations,
        )
        mark_cache_hit(cache)
        conversation.save(update_fields=['updated_at'])
        return JsonResponse({
            'ok': True,
            'answer': cache.answer,
            'citations': citations,
            'suggestions': cache.suggestions,
            'conversation_id': conversation.pk,
            'remaining': max(0, settings_obj.daily_question_limit - used - 1),
            'mode': 'cache',
        })

    contexts = retrieve_curriculum_context(source, lesson, question)
    if not contexts:
        answer = 'لا أجد في الصفحات المفهرسة نصًا كافيًا لهذا السؤال. اختر درسًا محددًا أو راجع صفحة الكتاب مع معلمك.'
        CurriculumMessage.objects.create(conversation=conversation, role='assistant', content=answer)
        conversation.save(update_fields=['updated_at'])
        return JsonResponse({
            'ok': True,
            'answer': answer,
            'citations': [],
            'suggestions': ['اختر درسًا محددًا'],
            'conversation_id': conversation.pk,
            'remaining': max(0, settings_obj.daily_question_limit - used - 1),
            'mode': 'source_only',
        })

    provider = get_provider()
    try:
        if not provider or not hasattr(provider, 'answer_curriculum_question'):
            raise AIServiceUnavailable('مزود الذكاء الاصطناعي غير متاح.')
        data, tokens, duration = provider.answer_curriculum_question(
            question=question,
            grade='الصف الرابع',
            subject=source.subject_name,
            lesson=lesson.title if lesson else '',
            page_contexts=contexts,
        )
        citations = map_provider_citations(contexts, data.get('citations', []))
        if data.get('answerable') and not citations:
            raise AIServiceUnavailable('تعذّر توثيق الإجابة من صفحات الكتاب.')
        stored_citations = [{'page_id': item['page_id']} for item in citations]
        CurriculumMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=data['answer'],
            citations=stored_citations,
            estimated_tokens=tokens,
            duration_ms=duration,
        )
        conversation.save(update_fields=['updated_at'])
        if data.get('answerable'):
            save_cached_answer(source, lesson, question, data['answer'], citations, data.get('suggestions', []))
        return JsonResponse({
            'ok': True,
            'answer': data['answer'],
            'citations': citations,
            'suggestions': data.get('suggestions', []),
            'conversation_id': conversation.pk,
            'remaining': max(0, settings_obj.daily_question_limit - used - 1),
            'mode': 'ai' if data.get('answerable') else 'source_only',
        })
    except AIServiceUnavailable as exc:
        logger.warning('Curriculum AI unavailable: %s', exc)
    except Exception:
        logger.exception('Unexpected curriculum AI failure')

    fallback = build_source_fallback_answer(source, lesson, question, contexts)
    if not fallback:
        return _error(
            'تعذّر تشغيل الشرح الذكي ولا يوجد نص كافٍ في الصفحات المختارة. اختر درسًا أو صفحة أوضح.',
            status=503,
            remaining=max(0, settings_obj.daily_question_limit - used - 1),
        )
    stored_citations = [{'page_id': page_id} for page_id in fallback['page_ids']]
    citations = hydrate_citations(stored_citations)
    CurriculumMessage.objects.create(
        conversation=conversation,
        role='assistant',
        content=fallback['answer'],
        citations=stored_citations,
    )
    conversation.save(update_fields=['updated_at'])
    return JsonResponse({
        'ok': True,
        'answer': fallback['answer'],
        'citations': citations,
        'suggestions': fallback['suggestions'],
        'conversation_id': conversation.pk,
        'remaining': max(0, settings_obj.daily_question_limit - used - 1),
        'mode': 'source_fallback',
    })


@login_required
def curriculum_source_page(request, page_id):
    page = get_object_or_404(
        CurriculumPage.objects.select_related('source', 'lesson'), pk=page_id,
    )
    if not _admin_only(request):
        student = _student(request)
        if not _student_is_supported(student) or page.source.status != 'published' or page.source.grade_level != 4:
            messages.error(request, 'هذه الصفحة غير متاحة لهذا الحساب.')
            return redirect('dashboard')
    if request.method == 'POST':
        if not _admin_only(request):
            return _error('ليس لديك صلاحية تعديل الصفحة.', status=403)
        page.visual_summary = str(request.POST.get('visual_summary') or '').strip()[:6000]
        page.needs_visual_review = request.POST.get('needs_visual_review') == 'on'
        page.save(update_fields=['visual_summary', 'needs_visual_review'])
        messages.success(request, 'تم حفظ الوصف البصري للصفحة.')
        return redirect('curriculum_source_page', page_id=page.pk)
    return render(request, 'school/curriculum_source_page.html', {
        'page': page,
        'is_admin': _admin_only(request),
    })


@login_required
def curriculum_assistant_admin(request):
    if not _admin_only(request):
        messages.error(request, 'هذه الصفحة متاحة لمدير المدرسة فقط.')
        return redirect('dashboard')
    settings_obj = CurriculumAssistantSettings.objects.order_by('pk').first()
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'save_settings':
            if not settings_obj:
                settings_obj = CurriculumAssistantSettings()
            try:
                daily_limit = min(100, max(1, int(request.POST.get('daily_question_limit') or 15)))
            except ValueError:
                daily_limit = 15
            settings_obj.enabled = request.POST.get('enabled') == 'on'
            settings_obj.source_only = True
            settings_obj.daily_question_limit = daily_limit
            settings_obj.updated_by = request.user
            settings_obj.save()
            _audit(request.user, 'تحديث إعدادات مساعد المنهاج')
            messages.success(request, 'تم حفظ إعدادات مساعد المنهاج.')
        elif action == 'import_package':
            uploaded = request.FILES.get('package')
            if not uploaded:
                messages.error(request, 'اختر حزمة JSON أو JSON.GZ للاستيراد.')
            else:
                try:
                    source, created = import_curriculum_package(uploaded, request.user)
                    _audit(request.user, 'استيراد مصدر منهاج', f'{source.title} — {source.source_sha256}')
                    messages.success(
                        request,
                        f'تم {"إضافة" if created else "التحقق من"} «{source.title}» '
                        f'({source.pages.count()} صفحة، {source.lessons.count()} درسًا).',
                    )
                except CurriculumPackageError as exc:
                    messages.error(request, str(exc))
        elif action in {'publish', 'archive'}:
            source = get_object_or_404(CurriculumSource, pk=request.POST.get('source_id'))
            if action == 'publish':
                if source.pages.count() != source.page_count or not source.lessons.exists():
                    messages.error(request, 'لا يمكن نشر المصدر قبل اكتمال الصفحات والدروس.')
                else:
                    with transaction.atomic():
                        CurriculumSource.objects.filter(
                            grade_level=source.grade_level,
                            term=source.term,
                            subject_code=source.subject_code,
                            status='published',
                        ).exclude(pk=source.pk).update(status='archived')
                        source.status = 'published'
                        source.published_at = timezone.now()
                        source.save(update_fields=['status', 'published_at'])
                    _audit(request.user, 'نشر مصدر منهاج', source.title)
                    messages.success(request, f'تم نشر «{source.title}» للطلاب.')
            else:
                source.status = 'archived'
                source.save(update_fields=['status'])
                _audit(request.user, 'أرشفة مصدر منهاج', source.title)
                messages.success(request, f'تمت أرشفة «{source.title}».')
        return redirect('curriculum_assistant_admin')

    sources = CurriculumSource.objects.prefetch_related('lessons').all()
    visual_review_count = CurriculumPage.objects.filter(needs_visual_review=True).count()
    review_pages = CurriculumPage.objects.filter(needs_visual_review=True).select_related(
        'source', 'lesson',
    )[:12]
    return render(request, 'school/curriculum_assistant_admin.html', {
        'settings_obj': settings_obj or curriculum_settings(),
        'sources': sources,
        'visual_review_count': visual_review_count,
        'review_pages': review_pages,
        'drive_connected': GoogleDriveService().is_connected(),
    })


@login_required
@require_POST
def curriculum_pdf_upload_start(request, source_id):
    if not _admin_only(request):
        return _error('ليس لديك صلاحية رفع مصدر المنهاج.', status=403)
    source = get_object_or_404(CurriculumSource, pk=source_id)
    try:
        payload = json.loads(request.body or b'{}')
    except (TypeError, ValueError, json.JSONDecodeError):
        return _error('بيانات الملف غير صالحة.')
    filename = Path(str(payload.get('name') or '').replace('\\', '/')).name[:300]
    mimetype = str(payload.get('type') or '').lower().split(';', 1)[0]
    guessed = (mimetypes.guess_type(filename)[0] or '').lower()
    try:
        size = int(payload.get('size') or 0)
    except (TypeError, ValueError):
        size = 0
    if Path(filename).suffix.lower() != '.pdf' or (mimetype or guessed) != 'application/pdf':
        return _error('يجب اختيار ملف PDF للكتاب.', code='unsupported_file')
    if size <= 0 or size > MAX_SOURCE_PDF_SIZE:
        return _error('حجم ملف الكتاب غير صالح أو أكبر من 100 ميغابايت.', code='file_too_large')
    supplied_sha256 = str(payload.get('sha256') or '').lower().strip()
    if supplied_sha256 != source.source_sha256:
        return _error(
            'هذا PDF لا يطابق بصمة الكتاب الذي أُنشئت منه حزمة الفهرسة.',
            code='source_hash_mismatch',
        )

    service = GoogleDriveService()
    if not service.is_connected():
        return _error(
            'Google Drive غير متصل. أعد ربط الحساب من إعدادات التخزين.',
            status=409,
            code='drive_reconnect',
            reconnect_url=reverse('ol_storage_settings'),
        )
    try:
        session_uri = service.start_resumable_upload(
            filename,
            'application/pdf',
            size,
            [CURRICULUM_FOLDER, f'الصف {source.grade_level}', source.subject_name, f'الفصل {source.term}'],
        )
    except Exception as exc:
        return _drive_error(exc)
    token = signing.dumps({
        'source_id': source.pk,
        'user_id': request.user.pk,
        'name': filename,
        'size': size,
        'session_uri': session_uri,
    }, salt=UPLOAD_TOKEN_SALT, compress=True)
    return JsonResponse({
        'ok': True,
        'upload_token': token,
        'chunk_url': reverse('curriculum_pdf_upload_chunk', args=[source.pk]),
        'chunk_size': UPLOAD_CHUNK_SIZE,
    })


@login_required
@require_POST
def curriculum_pdf_upload_chunk(request, source_id):
    if not _admin_only(request):
        return _error('ليس لديك صلاحية رفع مصدر المنهاج.', status=403)
    source = get_object_or_404(CurriculumSource, pk=source_id)
    try:
        token_data = signing.loads(
            request.headers.get('X-Upload-Token', ''),
            salt=UPLOAD_TOKEN_SALT,
            max_age=UPLOAD_TOKEN_MAX_AGE,
        )
    except signing.SignatureExpired:
        return _error('انتهت مهلة الرفع؛ أعد اختيار الملف.', status=409, code='upload_session_expired')
    except signing.BadSignature:
        return _error('جلسة الرفع غير صالحة.', code='invalid_upload_session')
    if token_data.get('source_id') != source.pk or token_data.get('user_id') != request.user.pk:
        return _error('جلسة الرفع لا تخص هذا المصدر.', status=403, code='invalid_upload_session')
    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', request.headers.get('Content-Range', ''))
    if not match:
        return _error('نطاق جزء الملف غير صالح.', code='invalid_chunk')
    start, end, total = (int(value) for value in match.groups())
    data = request.body
    if (
        total != int(token_data.get('size') or 0)
        or start < 0 or end < start or end >= total
        or len(data) != end - start + 1
        or len(data) > UPLOAD_CHUNK_SIZE
    ):
        return _error('حجم جزء الملف غير صالح.', code='invalid_chunk')
    try:
        result = GoogleDriveService().upload_resumable_chunk(
            token_data['session_uri'], data, start, end, total, 'application/pdf',
        )
    except Exception as exc:
        return _drive_error(exc)
    if result is None:
        return JsonResponse({'ok': True, 'complete': False, 'received': end + 1})
    if not result.get('id'):
        return _error('اكتمل النقل لكن Google Drive لم يُرجع معرّف الملف.', status=502)
    source.google_drive_file_id = result['id']
    source.google_drive_url = result.get('webViewLink', '')
    source.original_filename = result.get('name') or token_data['name']
    source.save(update_fields=['google_drive_file_id', 'google_drive_url', 'original_filename'])
    _audit(request.user, 'رفع PDF مصدر منهاج', source.title)
    return JsonResponse({'ok': True, 'complete': True, 'source_id': source.pk})
