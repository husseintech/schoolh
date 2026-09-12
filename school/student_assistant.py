import re
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .models import StudentAssistantKnowledge, StudentAssistantLog, StudentAssistantSettings


DEFAULT_DAILY_AI_LIMIT = 10
MAX_QUESTION_LENGTH = 500
MAX_REQUESTS_PER_HOUR = 60

ARABIC_NORMALIZATION = str.maketrans({
    'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ؤ': 'و', 'ئ': 'ي', 'ة': 'ه',
})


def student_short_name(full_name):
    """Use only the student's first and second names in the assistant."""
    parts = re.findall(r'\S+', (full_name or '').strip())
    return ' '.join(parts[:2]) or 'عزيزي الطالب'


def normalize_arabic(value):
    value = (value or '').strip().lower().translate(ARABIC_NORMALIZATION)
    value = re.sub(r'[\u064b-\u065f\u0670]', '', value)
    value = re.sub(r'[^\w\s]', ' ', value, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', value).strip()


def assistant_settings():
    settings_obj = StudentAssistantSettings.objects.order_by('pk').first()
    if settings_obj:
        return settings_obj
    return StudentAssistantSettings(
        enabled=True,
        educational_ai_enabled=True,
        daily_ai_limit=DEFAULT_DAILY_AI_LIMIT,
    )


def safe_internal_url(value):
    value = (value or '').strip()
    return value if value.startswith('/') and not value.startswith('//') else ''


def quick_prompts(student):
    prompts = [
        {'label': 'ما المطلوب مني؟', 'question': 'ما المهام المطلوبة مني الآن؟', 'icon': 'bi-list-check'},
        {'label': 'جدولي الدراسي', 'question': 'أين أجد جدولي الدراسي؟', 'icon': 'bi-calendar-week'},
        {'label': 'دروسي', 'question': 'أين أجد دروسي في التعلم المفتوح؟', 'icon': 'bi-book'},
        {'label': 'ملفي الطلابي', 'question': 'كيف أفتح ملفي الطلابي؟', 'icon': 'bi-person-vcard'},
    ]
    if not hasattr(student, 'survey'):
        prompts.insert(0, {'label': 'المسح الصحي', 'question': 'كيف أكمل المسح الصحي والاجتماعي؟', 'icon': 'bi-clipboard2-heart'})
    return prompts[:5]


def _contains(question, phrases):
    return any(normalize_arabic(phrase) in question for phrase in phrases)


def _result(answer, *, action_label='', action_url='', suggestions=None, mode='guided'):
    return {
        'answer': answer,
        'action_label': action_label,
        'action_url': safe_internal_url(action_url),
        'suggestions': list(suggestions or [])[:3],
        'mode': mode,
    }


def privacy_guard_answer(question):
    """Keep likely personal identifiers and private health details out of AI and logs."""
    normalized = normalize_arabic(question)
    private_phrases = (
        'رقم هويتي', 'هويتي هي', 'رقم الهويه هو',
        'رقم هاتفي', 'هاتفي هو', 'رقم جوالي', 'جوالي هو',
        'عنوان بيتي', 'حالتي الصحيه', 'تشخيصي', 'مرضي هو',
    )
    has_long_number = bool(re.search(r'(?<!\d)\d{8,12}(?!\d)', question))
    if has_long_number or _contains(normalized, private_phrases):
        return _result(
            'حرصًا على خصوصيتك، لا تكتب رقم الهوية أو الهاتف أو العنوان أو تفاصيل صحية خاصة في المحادثة. '
            'يمكنك سؤال الإدارة أو معلمك عن بيانات ملفك، أو صياغة سؤال تعليمي عام دون معلومات شخصية.',
            suggestions=['كيف أفتح ملفي؟', 'أين أجد دروسي؟'],
        )
    return None


def answer_guided_question(student, question):
    """Answer navigation and private student-state questions without using AI."""
    normalized = normalize_arabic(question)
    short_name = student_short_name(student.full_name)

    if _contains(normalized, ('السلام عليكم', 'مرحبا', 'اهلا', 'صباح الخير', 'مساء الخير')):
        return _result(
            f'أهلًا وسهلًا يا {short_name}. أنا مساعدك في المدرسة، ويمكنني إرشادك إلى مهامك وملفك وجدولك ودروس التعلم المفتوح.',
            suggestions=['ما المطلوب مني الآن؟', 'أين أجد دروسي؟', 'كيف أفتح ملفي؟'],
        )

    if _contains(normalized, ('المهام المطلوبة', 'المطلوب مني', 'ماذا علي', 'شو المطلوب')):
        pending = []
        if not hasattr(student, 'survey'):
            pending.append('إكمال المسح الصحي والاجتماعي')
        unread_messages = student.user.received_messages.filter(is_read=False).count()
        unread_notifications = student.user.notifications.filter(is_read=False).exclude(link__startswith='/messages/').count()
        if unread_messages:
            pending.append(f'قراءة {unread_messages} من الرسائل الجديدة')
        if unread_notifications:
            pending.append(f'مراجعة {unread_notifications} من الإشعارات الجديدة')
        if not pending:
            return _result(
                'أحسنت، لا توجد مهام أساسية جديدة مطلوبة منك الآن. يمكنك متابعة ملفك ودروس التعلم المفتوح.',
                action_label='فتح ملفي', action_url=reverse('student_detail', args=[student.pk]),
                suggestions=['أين أجد دروسي؟', 'أين جدولي الدراسي؟'],
            )
        return _result(
            'المطلوب منك الآن: ' + '، ثم '.join(pending) + '.',
            action_label='الذهاب إلى لوحتي', action_url=reverse('dashboard'),
            suggestions=['كيف أكمل المسح؟', 'افتح رسائلي', 'افتح إشعاراتي'],
        )

    if _contains(normalized, ('المسح الصحي', 'المسح الاجتماعي', 'الاستبيان', 'اكمل المسح')):
        if hasattr(student, 'survey'):
            answer = 'لقد أكملت المسح الصحي والاجتماعي بنجاح. شكرًا لاهتمامك ودقتك.'
        else:
            answer = 'اضغط الزر أدناه لفتح المسح الصحي والاجتماعي، واستعن بولي أمرك في تعبئته بدقة. تعامل المدرسة الإجابات بسرية.'
        return _result(answer, action_label='فتح المسح', action_url=reverse('survey_form'))

    if _contains(normalized, ('رسائلي', 'الرسائل', 'رساله')):
        count = student.user.received_messages.filter(is_read=False).count()
        return _result(
            f'لديك {count} من الرسائل غير المقروءة. يمكنك فتح رسائلك من الزر أدناه.',
            action_label='فتح رسائلي', action_url=reverse('student_messages'),
        )

    if _contains(normalized, ('اشعاراتي', 'الاشعارات', 'اشعار')):
        count = student.user.notifications.filter(is_read=False).exclude(link__startswith='/messages/').count()
        return _result(
            f'لديك {count} من الإشعارات الجديدة. راجعها حتى لا يفوتك أي تحديث من المدرسة.',
            action_label='فتح الإشعارات', action_url=reverse('notification_list'),
        )

    if _contains(normalized, ('ملفي', 'الملف الطلابي', 'بياناتي', 'حضوري', 'مستواي')):
        return _result(
            'يعرض ملفك الطلابي بياناتك المدرسية والحضور وأذونات المغادرة ومستواك والملاحظات المسموح لك برؤيتها.',
            action_label='فتح ملفي', action_url=reverse('student_detail', args=[student.pk]),
        )

    if _contains(normalized, ('غيابي', 'الغياب', 'غيبت')):
        count = student.absences.count()
        return _result(
            f'عدد أيام الغياب المسجلة في ملفك هو {count}. يمكنك مشاهدة التواريخ من تقرير غيابي.',
            action_label='عرض تقرير غيابي', action_url=reverse('student_absence_report'),
        )

    if _contains(normalized, ('جدولي', 'الجدول الدراسي', 'جدول الحصص', 'حصصي')):
        return _result(
            'ستجد جدول حصص صفك في لوحتك الطلابية، مرتبًا حسب أيام الأسبوع والحصص.',
            action_label='عرض جدولي', action_url=reverse('dashboard') + '#studentSchedule',
        )

    if _contains(normalized, ('اين اجد دروسي', 'افتح دروسي', 'التعلم المفتوح', 'مسار التعلم')):
        return _result(
            'توجد الدروس والأنشطة المنشورة لصفك في قسم التعلم المفتوح. يمكنك فتحها ومتابعة تقدمك من هناك.',
            action_label='فتح التعلم المفتوح', action_url=reverse('open_learning_list'),
            suggestions=['اشرح لي درسًا', 'ما معنى كلمة؟'],
        )

    if _contains(normalized, ('واتساب', 'مجموعه الصف', 'رابط الصف')):
        if not hasattr(student, 'survey'):
            return _result('يظهر رابط مجموعة صفك بعد إكمال المسح الصحي والاجتماعي.', action_label='إكمال المسح', action_url=reverse('survey_form'))
        return _result('يمكنك العثور على رابط مجموعة واتساب الخاصة بصفك داخل لوحتك الطلابية.', action_label='فتح لوحتي', action_url=reverse('dashboard'))

    if _contains(normalized, ('مساعده', 'ماذا تستطيع', 'كيف تساعدني')):
        return _result(
            'أساعدك في الوصول إلى مهامك وجدولك وملفك ودروسك، ويمكنني أيضًا شرح مفهوم دراسي أو إنشاء تدريب قصير مناسب لصفك.',
            suggestions=['ما المطلوب مني؟', 'أين أجد دروسي؟', 'اشرح لي مفهومًا دراسيًا'],
        )

    return None


def answer_from_knowledge(question):
    normalized = normalize_arabic(question)
    for item in StudentAssistantKnowledge.objects.filter(is_active=True).order_by('-priority', 'title'):
        keywords = [normalize_arabic(part) for part in re.split(r'[,،\n]+', item.keywords) if part.strip()]
        if any(keyword and keyword in normalized for keyword in keywords):
            return _result(
                item.answer,
                action_label=item.action_label,
                action_url=item.action_url,
                mode='knowledge',
            )
    return None


def build_learning_context(student, question, limit=5):
    """Select small, approved snippets relevant to the student's own class."""
    if not student.student_class_id:
        return []
    from open_learning.models import LearningLesson

    terms = {term for term in normalize_arabic(question).split() if len(term) >= 3}
    lessons = list(
        LearningLesson.objects.filter(
            status='published',
            student_classes=student.student_class,
        ).select_related('subject').distinct()[:30]
    )
    ranked = []
    for lesson in lessons:
        source = normalize_arabic(f'{lesson.title} {lesson.subject.name} {lesson.description}')
        score = sum(1 for term in terms if term in source)
        explanation = ''
        if lesson.ai_status == 'approved' and isinstance(lesson.ai_payload, dict):
            raw = lesson.ai_payload.get('explanation', '')
            if isinstance(raw, str):
                explanation = raw[:900]
            elif isinstance(raw, dict):
                explanation = str(raw.get('text') or raw.get('content') or '')[:900]
        ranked.append((score, lesson.pk, {
            'title': lesson.title,
            'subject': lesson.subject.name,
            'description': lesson.description[:600],
            'approved_explanation': explanation,
        }))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in ranked[:limit] if row[0] > 0] or [row[2] for row in ranked[:2]]


def hourly_request_limit_reached(student):
    since = timezone.now() - timedelta(hours=1)
    return StudentAssistantLog.objects.filter(student=student, created_at__gte=since).count() >= MAX_REQUESTS_PER_HOUR


def ai_questions_today(student):
    return StudentAssistantLog.objects.filter(
        student=student,
        mode='ai',
        created_at__date=timezone.localdate(),
    ).count()


def cached_ai_answer(student, question):
    return StudentAssistantLog.objects.filter(
        student=student,
        question__iexact=question.strip(),
        mode='ai',
        success=True,
        created_at__gte=timezone.now() - timedelta(days=7),
    ).exclude(answer='').order_by('-created_at').first()
