import time
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone

from .models import LearningLesson, LearningResource, LearningResourceLibrary
from .ai_forms import LessonBriefForm, SelectedSourceForm
from .services.ai_service import (
    AIServiceUnavailable, get_provider, lesson_content_hash, merge_section,
)
from .services.search_service import SearchService, SearchUnavailable
from .services.open_sources import teacher_search_links
from .services.usage import CACHE_OPERATION, log_usage, recent_ai_operation
from .views import _can_manage, _is_admin, _role


def _prompt_data(lesson, brief=None):
    classes = ', '.join(lesson.student_classes.values_list('name', flat=True))
    brief = brief if brief is not None else (lesson.ai_payload or {}).get('_brief', {})
    return {
        'grade': brief.get('grade') or classes or '',
        'subject': lesson.subject.name if lesson.subject else '',
        'lesson_title': lesson.title,
        'lesson_description': lesson.description,
        'objectives': (lesson.ai_payload or {}).get('objectives'),
        'brief': brief,
    }


def _link_reused_resource(lesson, src):
    """يربط مصدراً من درس آخر (مكتبة مركزية) بدون تكرار - نفس سجل المكتبة يُعاد استخدامه."""
    if lesson.resources.filter(library_id=src.library_id).exists():
        return False
    LearningResource.objects.create(
        lesson=lesson,
        title=src.title,
        resource_type=src.resource_type,
        url=src.url,
        description=src.description,
        status='approved',
        language=src.language,
        source_name=src.source_name,
        relevance_score=src.relevance_score,
        is_ai_generated=True,
        ai_generated_at=src.ai_generated_at,
        library=src.library,
    )
    return True


@login_required
def ai_generate_content(request, lesson_id):
    """✨ إنشاء محتوى ذكي للدرس — Cache First:
    المحتوى الموجود يقرأ من قاعدة البيانات دون أي استدعاء AI."""
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')

    brief_form = LessonBriefForm(request.POST if request.method == 'POST' else None,
                                 initial=(lesson.ai_payload or {}).get('_brief') or {
                                     'focus': lesson.description, 'duration': 40, 'learner_level': 'mixed'})
    if request.method == 'POST' and brief_form.is_valid():
        lesson.refresh_from_db()
        brief = brief_form.cleaned_data
        current_hash = lesson_content_hash(lesson, brief)

        if lesson.ai_payload and lesson.content_hash == current_hash:
            log_usage(request.user, lesson, CACHE_OPERATION, provider='cache')
            messages.info(request, 'المحتوى الذكي لهذا الدرس موجود مسبقاً — عُرض مباشرة من قاعدة البيانات دون أي استهلاك.')
            return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

        cached_lesson = (
            LearningLesson.objects
            .filter(content_hash=current_hash, ai_status='approved', ai_payload__isnull=False)
            .exclude(pk=lesson.pk)
            .first()
        )
        if cached_lesson:
            lesson.ai_payload = cached_lesson.ai_payload
            lesson.ai_status = 'pending'
            lesson.ai_reviewed_by = None
            lesson.ai_review_note = ''
            lesson.ai_generated_at = cached_lesson.ai_generated_at
            lesson.content_hash = current_hash
            lesson.save()
            linked = 0
            for src in cached_lesson.resources.filter(status='approved', is_ai_generated=True):
                if _link_reused_resource(lesson, src):
                    linked += 1
            log_usage(request.user, lesson, CACHE_OPERATION, provider='cache')
            msg = 'استُخدمت حزمة مطابقة للمواصفات؛ راجعها قبل اعتمادها لهذا الدرس.'
            if linked:
                msg += f' (رُبط {linked} من الموارد المخزنة)'
            messages.info(request, msg)
            return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

        provider = get_provider()
        if not provider:
            log_usage(request.user, lesson, 'generate_content', provider='none', success=False,
                      error='مزود الذكاء الاصطناعي غير مهيأ (AI_API_KEY)')
            messages.error(request, 'التوليد الحقيقي غير مفعّل. يحتاج مدير النظام إلى إعداد اتصال الذكاء الاصطناعي. لن نستبدل درسك بقالب عام.')
            return render(request, 'open_learning/ai_confirm.html', {
                'lesson': lesson, 'title': 'بناء حزمة تعلم مخصصة', 'brief_form': brief_form,
                'action_url': 'open_learning_ai_generate', 'cost_notice': True,
                'message': 'احتفظ بهذه التفاصيل حتى يفعّل مدير النظام اتصال الذكاء الاصطناعي.',
            })

        if recent_ai_operation(lesson.pk, 'generate_content'):
            messages.info(request, 'تم إنشاء المحتوى الذكي لهذا الدرس مؤخراً — اعرض النتيجة المحفوظة أو انتظر قليلاً.')
            return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

        try:
            data, tokens, duration_ms = provider.generate_lesson_content(_prompt_data(lesson, brief))
        except AIServiceUnavailable as exc:
            log_usage(request.user, lesson, 'generate_content', provider=provider.name, model=provider.model,
                      success=False, error=str(exc))
            messages.error(request, str(exc))
            return render(request, 'open_learning/ai_confirm.html', {
                'lesson': lesson, 'title': 'بناء حزمة تعلم مخصصة', 'brief_form': brief_form,
                'action_url': 'open_learning_ai_generate', 'cost_notice': True,
                'message': 'راجع التفاصيل وأعد المحاولة؛ لم يتغير المحتوى المحفوظ.',
            })

        data['_brief'] = brief
        data['_version'] = 2
        lesson.ai_payload = data
        lesson.ai_status = 'pending'
        lesson.content_hash = current_hash
        lesson.ai_generated_at = timezone.now()
        lesson.ai_reviewed_by = None
        lesson.ai_review_note = ''
        lesson.save()
        log_usage(request.user, lesson, 'generate_content', provider=provider.name, model=provider.model,
                  tokens=tokens, duration_ms=int(duration_ms or 0))
        messages.success(request, 'تم إنشاء المحتوى الذكي وهو الآن بانتظار مراجعتك واعتماده.')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

    return render(request, 'open_learning/ai_confirm.html', {
        'lesson': lesson,
        'title': 'بناء حزمة تعلم مخصصة',
        'brief_form': brief_form,
        'message': (
            'سيطلب النظام من الذكاء الاصطناعي إنشاء: الأهداف، الشرح المبسط، المفاهيم، الأسئلة التمهيدية، '
            'الأنشطة، أسئلة التقييم، أفكار التعلم التفاعلي، والاقتراحات الإثرائية. '
            'يُحفظ كل شيء بانتظار مراجعتك قبل عرضه للطلاب.'
        ),
        'action_url': 'open_learning_ai_generate',
        'cost_notice': True,
    })


SECTION_OPERATIONS = {
    'questions': 'regenerate_questions',
    'explanation': 'regenerate_explanation',
    'activities': 'regenerate_activities',
}


@login_required
def ai_regenerate_section(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    op_key = request.GET.get('op', request.POST.get('op', ''))
    if op_key not in SECTION_OPERATIONS:
        messages.error(request, 'عملية غير معروفة')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
    operation = SECTION_OPERATIONS[op_key]

    if request.method == 'POST':
        if not (lesson.ai_payload or {}).get('_brief'):
            messages.info(request, 'حدّد مفهوم الدرس والصف أولًا لبناء حزمة مخصصة.')
            return redirect('open_learning_ai_generate', lesson_id=lesson.pk)
        provider = get_provider()
        if not provider:
            log_usage(request.user, lesson, operation, provider='none', success=False,
                      error='مزود الذكاء الاصطناعي غير مهيأ (AI_API_KEY)')
            messages.error(request, 'اتصال الذكاء الاصطناعي غير مفعّل؛ يرجى مراجعة مدير النظام.')
            return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
        if recent_ai_operation(lesson.pk, operation):
            messages.info(request, 'تم توليد هذا القسم مؤخراً — اعرض النتيجة المحفوظة أو انتظر قليلاً.')
            return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

        try:
            data, tokens, duration_ms = provider.generate_section(_prompt_data(lesson), op_key)
        except AIServiceUnavailable as exc:
            log_usage(request.user, lesson, operation, provider=provider.name, model=provider.model,
                      success=False, error=str(exc))
            messages.error(request, str(exc))
            return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

        lesson.ai_payload = merge_section(lesson.ai_payload, op_key, data)
        lesson.ai_status = 'pending'
        lesson.ai_reviewed_by = None
        lesson.ai_review_note = ''
        lesson.ai_generated_at = timezone.now()
        lesson.save()
        log_usage(request.user, lesson, operation, provider=provider.name, model=provider.model,
                  tokens=tokens, duration_ms=int(duration_ms or 0))
        messages.success(request, 'تم توليد القسم الجديد وهو بانتظار مراجعتك.')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

    labels = {'questions': 'إنشاء أسئلة جديدة', 'explanation': 'إنشاء شرح جديد', 'activities': 'اقتراح أنشطة جديدة'}
    return render(request, 'open_learning/ai_confirm.html', {
        'lesson': lesson,
        'title': labels[op_key],
        'message': 'سيستبدل هذا الإجراء القسم الحالي بمنتج جديد يخضع لمراجعتك قبل اعتماده.',
        'action_url': 'open_learning_ai_section',
        'query': f'?op={op_key}',
        'cost_notice': True,
    })


def _execute_resource_search(request, lesson, operation, update_mode):
    current_hash = lesson_content_hash(lesson)
    reused = 0
    for cached in (LearningLesson.objects
                   .filter(content_hash=current_hash, ai_status='approved')
                   .exclude(pk=lesson.pk)):
        for src in cached.resources.filter(status='approved', is_ai_generated=True):
            if _link_reused_resource(lesson, src):
                reused += 1
    if reused:
        log_usage(request.user, lesson, CACHE_OPERATION, provider='cache')
        messages.info(request, f'استُخدمت {reused} مصادر مخزنة من دروس مطابقة — دون أي بحث أو استهلاك.')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

    if recent_ai_operation(lesson.pk, operation):
        messages.info(request, 'تم البحث عن مصادر لهذا الدرس مؤخراً — اعرض النتائج المحفوظة أو انتظر قليلاً.')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

    searcher = SearchService()
    brief = (lesson.ai_payload or {}).get('_brief', {})
    grade = f'الصف {brief["grade"]}' if brief.get('grade') else ', '.join(lesson.student_classes.values_list('name', flat=True))
    subject = lesson.subject.name if lesson.subject else ''
    started = time.monotonic()
    try:
        raw_results = searcher.search_all(lesson.title, grade, subject)
    except SearchUnavailable as exc:
        log_usage(request.user, lesson, operation, provider=searcher.provider, success=False, error=str(exc))
        messages.warning(request, str(exc))
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

    classified = [searcher.classify(item, lesson.title, grade, subject) for item in raw_results]
    if searcher.warnings:
        messages.info(request, 'بعض المكتبات لم تستجب؛ عرضنا نتائج المكتبات المتاحة. البحث الموجّه متاح أيضًا.')
    classified = searcher.deduplicate_by_domain(classified)
    classified = sorted(classified, key=lambda item: item['relevance_score'], reverse=True)[:8]
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Page IDs from the fixed public catalog API already identify existing pages.
        # Avoid a second round of HEAD requests that many reference sites disallow.
        checks = list(executor.map(
            lambda item: item.get('catalog_reference') or searcher.validate_url(item['url']), classified))
    valid_urls = {item['url'] for item, valid in zip(classified, checks) if valid}

    added = skipped_dup = skipped_invalid = skipped_archived = 0
    from .services.ai_service import normalize_url
    existing_urls = {normalize_url(url) for url in lesson.resources.values_list('url', flat=True)}
    for item in classified:
        norm = normalize_url(item['url'])
        if not norm or len(norm) > 500:
            continue
        if norm in existing_urls:
            skipped_dup += 1
            continue
        library = LearningResourceLibrary.objects.filter(normalized_url=norm).first()
        if library:
            if library.status == 'archived':
                skipped_archived += 1
                continue
            if lesson.resources.filter(Q(library_id=library.pk) | Q(url=item['url'])).exists():
                skipped_dup += 1
                continue
        else:
            if item['url'] not in valid_urls:
                skipped_invalid += 1
                continue
            library = LearningResourceLibrary.objects.create(
                title=item['title'][:200], url=item['url'], normalized_url=norm,
                resource_type=item['resource_type'], source_name=item['source_name'],
                language=item['language'], relevance_score=item['relevance_score'],
                grade_level=grade[:100], description=item['description'],
                status='pending', is_ai_generated=True, ai_generated_at=timezone.now(),
                created_by=request.user,
            )
        LearningResource.objects.create(
            lesson=lesson, title=library.title[:200], resource_type=library.resource_type,
            url=library.url, description=library.description, status='pending',
            language=library.language, source_name=library.source_name,
            relevance_score=library.relevance_score, is_ai_generated=True,
            ai_generated_at=library.ai_generated_at, library=library, created_by=request.user,
        )
        added += 1
        existing_urls.add(norm)

    duration_ms = int((time.monotonic() - started) * 1000)
    log_usage(request.user, lesson, operation, provider=searcher.provider, duration_ms=duration_ms,
              success=bool(added or skipped_dup), tokens=None)
    if not added:
        if skipped_dup:
            messages.info(request, 'المصادر المناسبة التي عثرنا عليها موجودة بالفعل في الدرس؛ لم نكررها.')
        else:
            messages.warning(request, 'لم نعثر على مصادر جديدة مناسبة يمكن إضافتها. جرّب عنوانًا أدق، أو أنشئ حزمة الدرس داخل الموقع من زر بناء حزمة تعلم مخصصة.')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
    summary = f'أُضيف {added} مصدر جديد (بانتظار اعتمادك).'
    if skipped_dup:
        summary += f' {skipped_dup} مكرراً تجاوزه النظام.'
    if skipped_invalid:
        summary += f' {skipped_invalid} رابطاً غير صالحاً حُذف.'
    if skipped_archived:
        summary += f' {skipped_archived} مصدراً مرفوضاً سابقاً لم يُعد.'
    messages.success(request, summary)
    return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)


@login_required
def ai_search_resources(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    selected_form = SelectedSourceForm(request.POST if request.method == 'POST' and request.POST.get('action') == 'add_selected' else None)
    if request.method == 'POST' and request.POST.get('action') == 'add_selected':
        if selected_form.is_valid():
            from .services.ai_service import normalize_url
            fields = selected_form.cleaned_data
            norm = normalize_url(fields['url'])
            if any(normalize_url(url) == norm for url in lesson.resources.values_list('url', flat=True)):
                messages.info(request, 'هذا الرابط موجود بالفعل؛ لم نكرره.')
            else:
                LearningResource.objects.create(lesson=lesson, **fields, status='pending', created_by=request.user,
                                                source_name='اختيار المعلم', is_ai_generated=False)
                messages.success(request, 'حُفظ المصدر بانتظار مراجعتك واعتماده قبل عرضه للطلاب.')
            return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
    elif request.method == 'POST':
        return _execute_resource_search(request, lesson, 'search_resources', update_mode=False)
    return render(request, 'open_learning/ai_confirm.html', {
        'lesson': lesson,
        'title': 'استوديو مصادر الدرس',
        'source_search': True,
        'selected_source_form': selected_form,
        'search_links': teacher_search_links(lesson),
        'message': (
            'البحث التلقائي يجلب مراجع من المكتبات المفتوحة، ويرتبها حسب كلمات الدرس ويحفظها بانتظار مراجعتك. '
            'هذه مراجع إثرائية وليست دروسًا مطابقة للصف تلقائيًا. للفيديو والأنشطة استخدم البحث الموجّه أدناه.'
        ),
        'action_url': 'open_learning_ai_search',
        'cost_notice': False,
    })


@login_required
def ai_update_resources(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    if request.method == 'POST':
        return _execute_resource_search(request, lesson, 'update_resources', update_mode=True)
    return render(request, 'open_learning/ai_confirm.html', {
        'lesson': lesson,
        'title': 'تحديث المصادر',
        'selected_source_form': SelectedSourceForm(),
        'source_search': True,
        'search_links': teacher_search_links(lesson),
        'message': (
            'سيتم البحث عن مصادر جديدة فقط، مع منع التكرار وعدم حذف المصادر القديمة. '
            'المكتبات المفتوحة الافتراضية لا تحتاج مفتاحًا مدفوعًا ولا تستخدم حصة Gemini.'
        ),
        'action_url': 'open_learning_ai_update',
        'cost_notice': False,
    })


@login_required
def ai_approve_content(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    if request.method == 'POST':
        note = request.POST.get('ai_review_note', '').strip()
        if lesson.ai_status == 'pending' and lesson.ai_payload:
            lesson.ai_status = 'approved'
            lesson.ai_reviewed_by = request.user
            lesson.ai_review_note = note
            lesson.save()
            messages.success(request, 'تم اعتماد المحتوى الذكي وسيظهر للطلاب عند نشر الدرس.')
        else:
            messages.warning(request, 'لا يوجد محتوى ذكي بانتظار الاعتماد.')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
    messages.error(request, 'اعتمد المحتوى من صفحة الدرس.')
    return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)


@login_required
def ai_approve_resource(request, lesson_id, resource_id):
    resource = get_object_or_404(LearningResource, pk=resource_id, lesson_id=lesson_id)
    if not _can_manage(request, resource.lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    if request.method == 'POST':
        resource.status = 'approved'
        resource.save()
        if resource.library:
            resource.library.status = 'approved'
            resource.library.save(update_fields=['status'])
        messages.success(request, 'تم اعتماد المصدر وسيظهر للطلاب.')
    return redirect('open_learning_lesson_detail', lesson_id=lesson_id)


@login_required
def ai_reject_resource(request, lesson_id, resource_id):
    resource = get_object_or_404(LearningResource, pk=resource_id, lesson_id=lesson_id)
    if not _can_manage(request, resource.lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    if request.method == 'POST':
        resource.status = 'archived'
        resource.save()
        messages.success(request, 'تم رفض المصدر وأُرشف دون حذفه.')
    return redirect('open_learning_lesson_detail', lesson_id=lesson_id)


@login_required
def ai_dashboard(request):
    if not _is_admin(request):
        messages.error(request, 'لوحة المراقبة لمدير المدرسة فقط')
        return redirect('open_learning_list')
    from .models import AIUsageLog

    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_logs = AIUsageLog.objects.filter(created_at__gte=month_start)
    stats = {
        'ai_requests_month': month_logs.filter(~Q(operation=CACHE_OPERATION)).count(),
        'success_month': month_logs.filter(~Q(operation=CACHE_OPERATION), success=True).count(),
        'failed_month': month_logs.filter(~Q(operation=CACHE_OPERATION), success=False).count(),
        'cache_hits': AIUsageLog.objects.filter(operation=CACHE_OPERATION).count(),
        'total_ai_calls': AIUsageLog.objects.filter(~Q(operation=CACHE_OPERATION)).count(),
        'generated_resources': LearningResourceLibrary.objects.filter(is_ai_generated=True).count(),
        'stored_resources': LearningResourceLibrary.objects.count(),
        'pending_resources': LearningResourceLibrary.objects.filter(status='pending').count(),
        'approved_resources': LearningResourceLibrary.objects.filter(status='approved').count(),
        'lessons_with_ai': LearningLesson.objects.exclude(ai_status='none').count(),
    }
    recent_logs = AIUsageLog.objects.select_related('user', 'lesson')[:30]
    provider = get_provider()
    searcher = SearchService()
    return render(request, 'open_learning/ai_dashboard.html', {
        'provider_configured': bool(provider),
        'provider_model': getattr(provider, 'model', ''),
        'search_provider': searcher.provider,
        'search_configured': searcher.provider != 'google' or bool(searcher.google_api_key and searcher.google_cse_id),
        'stats': stats,
        'recent_logs': recent_logs,
        'lesson': None,
    })
