import gzip
import io
import json
import re
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from .models import (
    CurriculumAnswerCache,
    CurriculumAssistantSettings,
    CurriculumLesson,
    CurriculumMessage,
    CurriculumPage,
    CurriculumSource,
)
from .student_assistant import normalize_arabic


MAX_QUESTION_LENGTH = 500
MAX_PACKAGE_BYTES = 15 * 1024 * 1024
MAX_UNCOMPRESSED_PACKAGE_BYTES = 30 * 1024 * 1024
DEFAULT_DAILY_LIMIT = 15
MAX_CONTEXT_PAGES = 6

STOP_WORDS = {
    'في', 'من', 'الى', 'علي', 'عن', 'ما', 'ماذا', 'كيف', 'هل', 'هو', 'هي', 'هذا', 'هذه',
    'لي', 'لنا', 'ثم', 'او', 'ان', 'اشرح', 'شرح', 'بسط', 'الدرس', 'درس', 'مثال', 'اعطني',
}


class CurriculumPackageError(ValueError):
    pass


def curriculum_settings():
    return CurriculumAssistantSettings.objects.order_by('pk').first() or CurriculumAssistantSettings(
        enabled=True,
        daily_question_limit=DEFAULT_DAILY_LIMIT,
        source_only=True,
    )


def is_grade_four(class_name):
    normalized = normalize_arabic(class_name)
    return bool(
        re.search(r'(^|\D)4(\D|$)', normalized)
        or any(word in normalized for word in ('الرابع', 'رابع', 'الصف الرابع'))
    )


def normalized_question(value):
    return normalize_arabic(value)[:MAX_QUESTION_LENGTH]


def question_tokens(value):
    return {
        token for token in normalized_question(value).split()
        if len(token) > 1 and token not in STOP_WORDS
    }


def questions_used_today(student):
    local_now = timezone.localtime()
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return CurriculumMessage.objects.filter(
        conversation__student=student,
        role='assistant',
        created_at__gte=day_start,
    ).count()


def hourly_limit_reached(student, limit=60):
    return CurriculumMessage.objects.filter(
        conversation__student=student,
        role='user',
        created_at__gte=timezone.now() - timedelta(hours=1),
    ).count() >= limit


def citation_payload(page):
    shown_page = page.printed_page_number or page.pdf_page_number
    page_kind = 'صفحة الكتاب' if page.printed_page_number else 'صفحة PDF'
    return {
        'page_id': page.pk,
        'pdf_page': page.pdf_page_number,
        'printed_page': page.printed_page_number,
        'label': f'{page.source.subject_name} — {page_kind} {shown_page}',
        'lesson': page.lesson.title if page.lesson else '',
        'url': reverse('curriculum_source_page', args=[page.pk]),
    }


def hydrate_citations(citations):
    page_ids = [item.get('page_id') for item in citations if isinstance(item, dict) and item.get('page_id')]
    pages = CurriculumPage.objects.select_related('source', 'lesson').in_bulk(page_ids)
    return [citation_payload(pages[page_id]) for page_id in page_ids if page_id in pages]


def retrieve_curriculum_context(source, lesson, question, max_pages=MAX_CONTEXT_PAGES):
    pages = source.pages.select_related('source', 'lesson')
    if lesson:
        pages = pages.filter(lesson=lesson)
    candidates = list(pages)
    if not candidates:
        return []

    normalized = normalized_question(question)
    tokens = question_tokens(question)
    generic_request = not tokens or any(
        phrase in normalized for phrase in ('اشرح الدرس', 'لخص الدرس', 'اختبرني', 'بسط الدرس')
    )
    ranked = []
    for page in candidates:
        searchable = ' '.join(filter(None, (page.normalized_text, normalize_arabic(page.visual_summary))))
        score = 0
        if normalized and normalized in searchable:
            score += 20
        for token in tokens:
            occurrences = searchable.count(token)
            if occurrences:
                score += min(occurrences, 4) * 3
        if lesson and page.pdf_page_number == lesson.start_pdf_page:
            score += 5
        if generic_request and lesson:
            score += max(0, 5 - (page.pdf_page_number - lesson.start_pdf_page))
        if searchable.strip():
            ranked.append((score, page))

    ranked.sort(key=lambda item: (-item[0], item[1].pdf_page_number))
    selected = []
    selected_ids = set()
    for score, page in ranked:
        if selected and score <= 0 and not lesson:
            break
        if page.pk not in selected_ids:
            selected.append(page)
            selected_ids.add(page.pk)
        if len(selected) >= max_pages:
            break
    if not selected:
        return []

    contexts = []
    for page in selected:
        body = '\n'.join(part for part in (page.text.strip(), page.visual_summary.strip()) if part).strip()
        if not body:
            continue
        contexts.append({
            'id': f'P{page.pk}',
            'page_id': page.pk,
            'printed_page': page.printed_page_number,
            'pdf_page': page.pdf_page_number,
            'lesson': page.lesson.title if page.lesson else '',
            'text': body[:2200],
        })
    return contexts


def map_provider_citations(contexts, citation_ids):
    by_id = {item['id']: item['page_id'] for item in contexts}
    page_ids = []
    for citation_id in citation_ids:
        page_id = by_id.get(str(citation_id))
        if page_id and page_id not in page_ids:
            page_ids.append(page_id)
    pages = CurriculumPage.objects.select_related('source', 'lesson').in_bulk(page_ids)
    return [citation_payload(pages[page_id]) for page_id in page_ids if page_id in pages]


def cached_answer(source, lesson, question):
    return CurriculumAnswerCache.objects.filter(
        source=source,
        lesson=lesson,
        normalized_question=normalized_question(question),
    ).first()


def save_cached_answer(source, lesson, question, answer, citations, suggestions):
    cache, _ = CurriculumAnswerCache.objects.update_or_create(
        source=source,
        lesson=lesson,
        normalized_question=normalized_question(question),
        defaults={
            'answer': answer,
            'citations': [
                {'page_id': item['page_id']} for item in citations if item.get('page_id')
            ],
            'suggestions': suggestions[:3],
        },
    )
    return cache


def _positive_int(value, label, *, allow_none=False):
    if value in (None, '') and allow_none:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise CurriculumPackageError(f'الحقل «{label}» يجب أن يكون رقمًا صحيحًا.') from exc
    if number <= 0:
        raise CurriculumPackageError(f'الحقل «{label}» يجب أن يكون أكبر من صفر.')
    return number


def read_curriculum_package(uploaded):
    if getattr(uploaded, 'size', 0) > MAX_PACKAGE_BYTES:
        raise CurriculumPackageError('حزمة المنهاج أكبر من الحد المسموح (15 ميغابايت).')
    raw = uploaded.read(MAX_PACKAGE_BYTES + 1)
    if len(raw) > MAX_PACKAGE_BYTES:
        raise CurriculumPackageError('حزمة المنهاج أكبر من الحد المسموح (15 ميغابايت).')
    try:
        if raw.startswith(b'\x1f\x8b') or str(getattr(uploaded, 'name', '')).lower().endswith('.gz'):
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as archive:
                raw = archive.read(MAX_UNCOMPRESSED_PACKAGE_BYTES + 1)
        if len(raw) > MAX_UNCOMPRESSED_PACKAGE_BYTES:
            raise CurriculumPackageError('حزمة المنهاج بعد فك الضغط أكبر من الحد المسموح.')
        payload = json.loads(raw.decode('utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurriculumPackageError('ملف الحزمة ليس JSON أو JSON.GZ صالحًا.') from exc
    if not isinstance(payload, dict) or payload.get('schema_version') != 1:
        raise CurriculumPackageError('إصدار حزمة المنهاج غير مدعوم.')
    return payload


def validate_curriculum_package(payload):
    source_data = payload.get('source')
    lessons = payload.get('lessons')
    pages = payload.get('pages')
    if not isinstance(source_data, dict) or not isinstance(lessons, list) or not isinstance(pages, list):
        raise CurriculumPackageError('الحزمة لا تحتوي المصدر والدروس والصفحات بالشكل المطلوب.')

    subject_code = str(source_data.get('subject_code') or '').strip()
    valid_subjects = {code for code, _ in CurriculumSource.SUBJECT_CHOICES}
    if subject_code not in valid_subjects:
        raise CurriculumPackageError('رمز المادة في الحزمة غير معتمد.')
    sha256 = str(source_data.get('sha256') or '').lower().strip()
    if not re.fullmatch(r'[0-9a-f]{64}', sha256):
        raise CurriculumPackageError('بصمة ملف المصدر SHA-256 غير صالحة.')

    page_count = _positive_int(source_data.get('page_count'), 'عدد الصفحات')
    if len(pages) != page_count:
        raise CurriculumPackageError('عدد الصفحات في الحزمة لا يطابق عدد صفحات المصدر.')
    clean_lessons = []
    lesson_orders = set()
    for index, item in enumerate(lessons, start=1):
        if not isinstance(item, dict) or not str(item.get('title') or '').strip():
            raise CurriculumPackageError(f'بيانات الدرس رقم {index} غير مكتملة.')
        order = _positive_int(item.get('lesson_order', index), 'ترتيب الدرس')
        if order in lesson_orders:
            raise CurriculumPackageError('ترتيب الدروس مكرر داخل الحزمة.')
        lesson_orders.add(order)
        start_pdf = _positive_int(item.get('start_pdf_page'), 'أول صفحة PDF')
        end_pdf = _positive_int(item.get('end_pdf_page'), 'آخر صفحة PDF')
        if start_pdf > end_pdf or end_pdf > page_count:
            raise CurriculumPackageError(f'نطاق صفحات الدرس «{item.get("title")}» غير صالح.')
        clean_lessons.append({
            'unit_title': str(item.get('unit_title') or '').strip()[:240],
            'unit_order': _positive_int(item.get('unit_order', 1), 'ترتيب الوحدة'),
            'lesson_order': order,
            'title': str(item['title']).strip()[:240],
            'start_printed_page': _positive_int(item.get('start_printed_page'), 'أول صفحة مطبوعة', allow_none=True),
            'end_printed_page': _positive_int(item.get('end_printed_page'), 'آخر صفحة مطبوعة', allow_none=True),
            'start_pdf_page': start_pdf,
            'end_pdf_page': end_pdf,
        })
    clean_lessons.sort(key=lambda item: item['lesson_order'])
    previous_end = 0
    for lesson in clean_lessons:
        if lesson['start_pdf_page'] <= previous_end:
            raise CurriculumPackageError('نطاقات صفحات الدروس متداخلة أو غير مرتبة.')
        previous_end = lesson['end_pdf_page']

    clean_pages = []
    seen_pages = set()
    for item in pages:
        if not isinstance(item, dict):
            raise CurriculumPackageError('يوجد سجل صفحة غير صالح في الحزمة.')
        pdf_page = _positive_int(item.get('pdf_page_number'), 'رقم صفحة PDF')
        if pdf_page in seen_pages or pdf_page > page_count:
            raise CurriculumPackageError('أرقام صفحات PDF مكررة أو خارج نطاق الكتاب.')
        seen_pages.add(pdf_page)
        text = str(item.get('text') or '').strip()
        visual_summary = str(item.get('visual_summary') or '').strip()
        clean_pages.append({
            'pdf_page_number': pdf_page,
            'printed_page_number': _positive_int(item.get('printed_page_number'), 'رقم الصفحة المطبوع', allow_none=True),
            'text': text,
            'normalized_text': normalize_arabic(text),
            'visual_summary': visual_summary,
            'needs_visual_review': bool(item.get('needs_visual_review')),
        })
    if seen_pages != set(range(1, page_count + 1)):
        raise CurriculumPackageError('الحزمة يجب أن تحتوي جميع صفحات PDF مرة واحدة.')

    clean_source = {
        'grade_level': _positive_int(source_data.get('grade_level'), 'الصف'),
        'term': _positive_int(source_data.get('term'), 'الفصل'),
        'subject_code': subject_code,
        'subject_name': str(source_data.get('subject_name') or '').strip()[:120],
        'title': str(source_data.get('title') or '').strip()[:240],
        'edition': str(source_data.get('edition') or '').strip()[:120],
        'original_filename': str(source_data.get('original_filename') or '').strip()[:300],
        'source_sha256': sha256,
        'page_count': page_count,
    }
    if not all((clean_source['subject_name'], clean_source['title'], clean_source['original_filename'])):
        raise CurriculumPackageError('بيانات تعريف المصدر غير مكتملة.')
    return clean_source, clean_lessons, clean_pages


@transaction.atomic
def import_curriculum_package(uploaded, user):
    source_data, lessons_data, pages_data = validate_curriculum_package(read_curriculum_package(uploaded))
    existing = CurriculumSource.objects.filter(source_sha256=source_data['source_sha256']).first()
    if existing and existing.pages.count() == source_data['page_count'] and existing.lessons.exists():
        return existing, False
    if existing and existing.status == 'published':
        raise CurriculumPackageError('لا يمكن استبدال صفحات مصدر منشور. ارفع إصدارًا جديدًا ببصمة مختلفة.')

    source, created = CurriculumSource.objects.update_or_create(
        source_sha256=source_data.pop('source_sha256'),
        defaults={**source_data, 'created_by': user},
    )
    source.pages.all().delete()
    source.lessons.all().delete()
    lessons = [CurriculumLesson(source=source, **item) for item in lessons_data]
    CurriculumLesson.objects.bulk_create(lessons)
    lesson_rows = list(source.lessons.order_by('lesson_order'))

    page_objects = []
    for page_data in pages_data:
        lesson = next((
            row for row in lesson_rows
            if row.start_pdf_page <= page_data['pdf_page_number'] <= row.end_pdf_page
        ), None)
        page_objects.append(CurriculumPage(source=source, lesson=lesson, **page_data))
    CurriculumPage.objects.bulk_create(page_objects, batch_size=100)
    return source, created


def mark_cache_hit(cache):
    CurriculumAnswerCache.objects.filter(pk=cache.pk).update(hits=F('hits') + 1, updated_at=timezone.now())
