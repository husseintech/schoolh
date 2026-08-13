"""طبقة تجريد مزود الذكاء الاصطناعي.

AIService هي الواجهة الوحيدة التي يستخدمها النظام:
    - generate_lesson_content()
    - generate_section()
    - classify_resources()  (تقييم القواعد بدون AI - مجاني)

لا يُربط النظام بأي مزود مباشرة. لاحقاً يمكن إضافة مزود جديد
بإنشاء صنف يطبق نفس الواجهة وتغيير مزود واحد فقط في get_provider().

المفاتيح تأتي من متغيرات البيئة فقط (AI_API_KEY) ولا تُطبع في أي مكان.
"""
import hashlib
import json
import os
import re
import time

import requests
from django.conf import settings
from django.utils import timezone

AI_CONTENT_VERSION = 1


class AIServiceUnavailable(Exception):
    """يُرمى عندما لا يتوفر مزود AI مهيأ أو يفشل الطلب."""


def get_provider():
    """يعيد مزود AI مهيأ أو None إذا لم يتوفر.

    AI_PROVIDER: gemini | mock | none
        - gemini: يتطلب AI_API_KEY من متغيرات البيئة.
        - mock: يستخدم محلياً فقط (تلقائياً عند DEBUG=True) لإكمال سير العمل بدون تكلفة.
        - none: بدون AI - يعمل النظام كاملاً مع المحتوى المخزن.
    """
    provider = os.getenv('AI_PROVIDER', 'mock' if settings.DEBUG else 'none').strip().lower()
    if provider == 'gemini':
        key = os.getenv('AI_API_KEY', '').strip()
        if key:
            return GeminiProvider(key=key, model=os.getenv('AI_MODEL', 'gemini-2.0-flash').strip())
        return None
    if provider == 'mock':
        return MockProvider()
    return None


def lesson_content_hash(lesson):
    """بصمة محتوى الدرس: الصف + المادة + العنوان + الوصف + اللغة + الإصدار."""
    raw = '|'.join([
        str(lesson.student_class_id),
        str(lesson.subject_id),
        lesson.title.strip().lower(),
        lesson.description.strip().lower(),
        'ar',
        f'v{AI_CONTENT_VERSION}',
    ])
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def normalize_url(url):
    """توحيد الرابط لمنع التكرار (حذف الترويسة، www، شريحة النهاية، معلمات التتبع)."""
    url = url.strip()
    if not url:
        return ''
    url = url.split('?')[0].split('#')[0]
    url = url.rstrip('/')
    url = url.replace('http://', '').replace('https://', '')
    url = re.sub(r'^www\.', '', url, flags=re.IGNORECASE)
    url = url.lower()
    if url.startswith('youtu.be/'):
        url = 'youtube.com/watch?v=' + url.split('/', 1)[1]
    if url.startswith('m.youtube.com/') or url.startswith('youtube.com/'):
        url = 'youtube.com/' + url.split('/', 1)[1]
    return url


class GeminiProvider:
    """مزود Gemini عبر REST API (خطة مجانية - بلا بطاقة).

    يُستدعى فقط عند الطلب اليدوي لإنشاء/تحديث المحتوى.
    """

    def __init__(self, key, model='gemini-2.0-flash'):
        self.key = key
        self.model = model
        self.name = 'gemini'

    def _call(self, prompt, max_tokens=4096):
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent'
        body = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {
                'temperature': 0.4,
                'maxOutputTokens': max_tokens,
                'responseMimeType': 'application/json',
            },
        }
        started = time.monotonic()
        try:
            resp = requests.post(url, params={'key': self.key}, json=body, timeout=90)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise AIServiceUnavailable(f'تعذر الاتصال بمزود الذكاء الاصطناعي: {exc}') from exc
        duration_ms = int((time.monotonic() - started) * 1000)
        try:
            text = data['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError, TypeError) as exc:
            raise AIServiceUnavailable('استجابة غير متوقعة من مزود الذكاء الاصطناعي') from exc
        usage = data.get('usageMetadata', {}) or {}
        tokens = (usage.get('promptTokenCount') or 0) + (usage.get('candidatesTokenCount') or 0)
        return _parse_json_text(text), tokens, duration_ms

    def generate_lesson_content(self, prompt_data):
        return self._call(_full_pack_prompt(prompt_data))

    def generate_section(self, prompt_data, section):
        return self._call(_section_prompt(prompt_data, section))


class MockProvider:
    """مزود محلي تجريبي (DEBUG فقط) لاختبار سير العمل كاملاً بدون مفتاح.

    يولّد محتوى منظم بنفس الشكل الذي يعيده المزود الحقيقي.
    """

    name = 'mock'
    model = 'mock'

    def __init__(self):
        self.key = ''
        self.model = 'mock'

    def generate_lesson_content(self, prompt_data):
        title = prompt_data['lesson_title']
        subject = prompt_data['subject']
        grade = prompt_data['grade']
        payload = {
            'objectives': [
                f'أن يشرح الطالب المفاهيم الأساسية في {title} بأسلوبه الخاص.',
                f'أن يميّز الطالب بين الأمثلة الصحيحة وغير الصحيحة ضمن درس {title}.',
                'أن يطبّق الطالب ما تعلمه في حل تمارين وأنشطة عملية.',
            ],
            'explanation': (
                f'في درس {title} لمادة {subject} (الصف {grade}) نبدأ من الفكرة العامة، ثم نقسّم الموضوع '
                'إلى أجزاء صغيرة مترابطة، ونستخدم أمثلة من الحياة اليومية لتقريب المعنى. بعد كل فكرة '
                'نطرح سؤالاً سريعاً للتأكد من الفهم، ثم ننتقل للفكرة التالية حتى يكتمل المفهوم.'
            ),
            'concepts': ['الفكرة الرئيسية', 'المفردات المفتاحية', 'العلاقات بين المفاهيم'],
            'pre_questions': [
                f'ما الذي تعرفه مسبقاً عن {title}؟',
                'ما الأسئلة التي تريد الإجابة عنها في نهاية هذا الدرس؟',
            ],
            'activities': [
                'نشاط فردي: تلخيص الفكرة الرئيسية في ثلاث جمل.',
                'نشاط جماعي: مناقشة موجهة حول أمثلة من الواقع.',
                'نشاط تطبيقي: حل التمارين المرافقة للدرس.',
            ],
            'evaluation_questions': [
                f'عرّف المصطلحات الأساسية الواردة في درس {title}.',
                'قارن بين المفهوم الجديد وما يشبهه مما درسته سابقاً.',
                'مسألة تطبيقية قصيرة تقيس فهم الموضوع بشكل عام.',
            ],
            'interactive_ideas': [
                'مسابقة سريعة بين المجموعات (أسئلة وأجوبة).',
                'رسم خريطة مفاهيم جماعية على السبورة.',
                'محاكاة تفاعلية بسيطة عبر رابط تعليمي آمن.',
            ],
            'external_suggestions': [
                'البحث عن فيديو تعليمي قصير باللغة العربية عن الموضوع.',
                'التجول في مكتبة المدرسة أو منصة رقمية معتمدة للاطلاع على مصادر إثرائية.',
            ],
        }
        return payload, 0, 0

    def generate_section(self, prompt_data, section):
        payload, _, _ = self.generate_lesson_content(prompt_data)
        if section == 'explanation':
            return {'explanation': payload['explanation']}, 0, 0
        if section == 'questions':
            return {'pre_questions': payload['pre_questions'], 'evaluation_questions': payload['evaluation_questions']}, 0, 0
        if section == 'activities':
            return {'activities': payload['activities'], 'interactive_ideas': payload['interactive_ideas']}, 0, 0
        return payload, 0, 0


def _parse_json_text(text):
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIServiceUnavailable('استجابة الذكاء الاصطناعي غير صالحة (JSON)') from exc


def _base_prompt(prompt_data):
    return (
        'أنت مساعد تربوي لبناء مكتبة تعلم مدرسية. أجب دائماً بصيغة JSON صالحة فقط، '
        'بلا أي نص خارج كائن JSON، وباللغة العربية الفصحى المبسطة المناسبة للصف الدراسي.\n'
        'البيانات:\n'
        f'الصف الدراسي: {prompt_data["grade"]}\n'
        f'المادة: {prompt_data["subject"]}\n'
        f'عنوان الدرس: {prompt_data["lesson_title"]}\n'
        f'وصف الدرس: {prompt_data.get("lesson_description") or "(بدون وصف)"}\n'
        f'الأهداف الحالية: {prompt_data.get("objectives") or "(لا توجد)"}\n'
        'القواعد:\n'
        '- اكتب محتوى أصلياً مبسطاً، لا تنسخ نصوصاً محمية بحقوق النشر.\n'
        '- لا تخترع روابط خارجية إطلاقاً: external_suggestions نصية وصفية فقط بدون URLs.\n'
        '- اجعل كل قائمة بأسلوب لغة عربية سليمة.\n'
    )


def _full_pack_prompt(prompt_data):
    return _base_prompt(prompt_data) + (
        'أعد كائن JSON بالمفاتيح التالية فقط:\n'
        '{\n'
        '  "objectives": ["3-4 أهداف تعلم"],\n'
        '  "explanation": "شرح مبسط للدرس بفقرات مناسبة للصف",\n'
        '  "concepts": ["5-8 كلمات ومفاهيم أساسية"],\n'
        '  "pre_questions": ["2-3 أسئلة تمهيدية"],\n'
        '  "activities": ["3-4 أنشطة صفية متنوعة"],\n'
        '  "evaluation_questions": ["3-5 أسئلة تقييم"],\n'
        '  "interactive_ideas": ["2-3 أفكار للتعلم التفاعلي"],\n'
        '  "external_suggestions": ["اقتراحات نصية لمصادر خارجية بدون روابط"]\n'
        '}\n'
    )


def _section_prompt(prompt_data, section):
    base = _base_prompt(prompt_data)
    if section == 'explanation':
        return base + 'أعد كائن JSON بالمفاتيح التالية فقط: {"explanation": "شرح جديد مبسط للدرس"}'
    if section == 'questions':
        return base + 'أعد كائن JSON بالمفاتيح التالية فقط: {"pre_questions": ["3 أسئلة تمهيدية جديدة"], "evaluation_questions": ["5 أسئلة تقييم جديدة"]}'
    if section == 'activities':
        return base + 'أعد كائن JSON بالمفاتيح التالية فقط: {"activities": ["4 أنشطة جديدة"], "interactive_ideas": ["3 أفكار تعلم تفاعلي جديدة"]}'
    raise AIServiceUnavailable(f'قسم غير معروف: {section}')


def merge_section(payload, section, data):
    """يدمج نتيجة توليد قسم داخل الحزمة الحالية بدون فقدان الأقسام الأخرى."""
    payload = dict(payload)
    for key, value in data.items():
        if isinstance(value, list):
            payload[key] = value
        else:
            payload[key] = value
    return payload
