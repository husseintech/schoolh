"""محرك البحث عن المصادر التعليمية.

يفصل البحث عن المصادر عن توليد المحتوى بالذكاء الاصطناعي:
    - روابط حقيقية فقط من نتائج البحث الفعلية (ممنوع اختراع URLs).
    - يتحقق من صلاحية الروابط (HTTP status) قبل الحفظ.
    - يصنّف النتائج بالقواعد (بدون AI) ويعطي relevance_score واللغة واسم المصدر.
    - يستعلامات متعددة حسب نوع المصدر (فيديو/شرح/محاكاة/نشاط/تجربة/صور).
    - يحد من تكرار نفس الموقع (تنويع المصادر).

المزوّدات:
    - duckduckgo: افتراضي، بدون مفتاح.
    - google: اختياري عبر GOOGLE_CSE_ID + GOOGLE_CSE_API_KEY (رصيد مجاني يومي).
"""
import os
import re
import time
from urllib.parse import unquote, urlparse, parse_qs

import requests

from .ai_service import normalize_url

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

ARABIC_RE = re.compile(r'[\u0600-\u06FF]')
TITLE_FILLERS = re.compile(r'[^\w\u0600-\u06FF ]+', re.UNICODE)
STOP_WORDS = {
    'درس', 'شرح', 'تعليم', 'تعليمي', 'موضوع', 'الوحدة', 'الفصل', 'الصف', 'الأساسي',
    'الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس', 'السادس', 'السابع', 'الثامن', 'التاسع', 'العاشر',
    'في', 'من', 'إلى', 'على', 'عن', 'مع', 'و', 'أو', 'ال',
}

QUERY_TEMPLATES = [
    {'group': 'general', 'query': '"{title}" {grade} {subject} شرح عربي'},
    {'group': 'video', 'query': '"{title}" {grade} {subject} فيديو تعليمي'},
    {'group': 'video', 'query': '"{title}" {subject} درس يوتيوب عربي'},
    {'group': 'simulation', 'query': '"{title}" {subject} محاكاة تفاعلية'},
    {'group': 'activity', 'query': '"{title}" {subject} نشاط تعليمي'},
    {'group': 'experiment', 'query': '"{title}" {subject} تجربة عملية'},
    {'group': 'image', 'query': '"{title}" {subject} صورة رسم توضيحي'},
    {'group': 'reading', 'query': '"{title}" {subject} مقال شرح وملخص pdf'},
]

IMAGE_EXT_RE = re.compile(r'\.(png|jpe?g|gif|webp|svg)(\?|$)', re.IGNORECASE)
KNOWN_EDUCATIONAL = ['youtube.com', 'moe.gov', 'google', 'wikipedia', 'britannica', 'khanacademy',
                     'edpuzzle', 'classroom.google', 'arabiaeducators', 'almo7eb', 'ia.edu', 'quipoquiz']


def _words(value):
    return [w for w in TITLE_FILLERS.sub(' ', value or '').lower().split() if w]


def _core_lesson_words(value):
    return [w for w in _words(value) if len(w) > 2 and w not in STOP_WORDS]


class SearchService:
    """يبحث ويصنف النتائج. لا يخزن في قاعدة البيانات أبداً."""

    def __init__(self):
        self.provider = os.getenv('SEARCH_PROVIDER', 'duckduckgo').strip().lower()
        self.google_cse_id = os.getenv('GOOGLE_CSE_ID', '').strip()
        self.google_api_key = os.getenv('GOOGLE_CSE_API_KEY', '').strip()
        self.domain_cap = int(os.getenv('SEARCH_DOMAIN_CAP', '2'))

    def search_all(self, lesson_title, grade, subject, max_per_group=4):
        results = []
        seen_urls = set()
        for spec in QUERY_TEMPLATES:
            query = spec['query'].format(title=lesson_title, grade=grade, subject=subject)
            try:
                raw = self._search(query, limit=max_per_group)
            except SearchUnavailable:
                continue
            group = spec['group']
            for item in raw:
                norm = normalize_url(item['url'])
                if not norm or norm in seen_urls:
                    continue
                seen_urls.add(norm)
                item['group'] = group
                results.append(item)
            time.sleep(0.4)
        return results

    def _search(self, query, limit):
        if self.provider == 'google' and self.google_cse_id and self.google_api_key:
            return self._search_google(query, limit)
        return self._search_duckduckgo(query, limit)

    def _search_duckduckgo(self, query, limit):
        url = 'https://html.duckduckgo.com/html/'
        try:
            resp = requests.post(url, data={'q': query}, headers={'User-Agent': USER_AGENT}, timeout=25)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise SearchUnavailable(f'تعذر البحث: {exc}') from exc
        html = resp.text
        items = []
        for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
            href, title_html = m.group(1), m.group(2)
            real_url = self._extract_duckduckgo_url(href)
            if not real_url or not real_url.startswith('http'):
                continue
            title = re.sub(r'<[^>]+>', '', title_html)
            title = re.sub(r'\s+', ' ', title).strip()
            snippet = ''
            sm = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', html[html.find(href):], re.IGNORECASE | re.DOTALL)
            if sm:
                snippet = re.sub(r'<[^>]+>', '', sm.group(1))
                snippet = re.sub(r'\s+', ' ', snippet).strip()
            if title and real_url.startswith(('https://', 'http://')):
                items.append({'title': title, 'url': real_url, 'snippet': snippet})
            if len(items) >= limit:
                break
        if not items:
            raise SearchUnavailable('لا توجد نتائج بحث')
        return items

    @staticmethod
    def _extract_duckduckgo_url(href):
        if href.startswith('//duckduckgo.com/l/'):
            qs = parse_qs(urlparse(href).query)
            if 'uddg' in qs:
                return unquote(qs['uddg'][0])
        if href.startswith('http'):
            return href
        return None

    def _search_google(self, query, limit):
        url = 'https://www.googleapis.com/customsearch/v1'
        params = {'key': self.google_api_key, 'cx': self.google_cse_id, 'q': query, 'num': min(limit, 10), 'hl': 'ar'}
        try:
            resp = requests.get(url, params=params, timeout=25)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise SearchUnavailable(f'تعذر البحث: {exc}') from exc
        items = [{'title': i.get('title', ''), 'url': i.get('link', ''),
                  'snippet': re.sub(r'\s+', ' ', i.get('snippet', '')).strip()} for i in data.get('items', [])]
        if not items:
            raise SearchUnavailable('لا توجد نتائج بحث')
        return items

    def validate_url(self, url):
        try:
            resp = requests.head(url, headers={'User-Agent': USER_AGENT}, timeout=10, allow_redirects=True)
            if resp.status_code >= 400:
                resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=10, stream=True)
            return resp.status_code < 400
        except requests.RequestException:
            return False

    def is_relevant(self, item, lesson_title, subject=''):
        """حاجز إلزامي قبل الحفظ: يجب أن تشير النتيجة فعلاً إلى موضوع الدرس.

        نبحث في العنوان والوصف معاً. إذا كان عنوان الدرس عاماً جداً ولا يحتوي كلمات
        دلالية، نلزم على الأقل ظهور المادة. هذا يمنع مرور نتيجة تعليمية من مادة أخرى.
        """
        haystack = ' '.join(_words((item.get('title') or '') + ' ' + (item.get('snippet') or '')))
        lesson_terms = _core_lesson_words(lesson_title)
        subject_terms = [w for w in _words(subject) if len(w) > 2 and w not in STOP_WORDS]

        if lesson_terms:
            # كلمة موضوع واحدة على الأقل يجب أن تكون موجودة بوضوح في عنوان/وصف النتيجة.
            if not any(term in haystack for term in lesson_terms):
                return False
            # إذا ظهرت المادة صراحة في البيانات، فهذا يعزز المطابقة؛ عدم ظهورها لا يرفض
            # المصدر لأن كثيراً من نتائج الويب الجيدة تذكر الموضوع دون اسم المادة.
            return True

        # عناوين عامة مثل «الدرس الأول»: لا نسمح بنتيجة من مادة مختلفة.
        if subject_terms:
            return any(term in haystack for term in subject_terms)
        return False

    def classify(self, item, lesson_title, grade, subject):
        url = item['url']
        title = item.get('title', '')
        snippet = item.get('snippet', '')
        text = title + ' ' + snippet

        if ARABIC_RE.search(text):
            language = 'ar'
        elif re.search(r'[a-zA-Z]', text):
            language = 'en'
        else:
            language = 'other'

        group = item.get('group', 'general')
        rtype = self._detect_type(group, url, text)
        source_name = self._source_name(url)
        description = (snippet[:220] or f'مصدر عن {lesson_title}').strip()

        score = 35
        score += 20 if language == 'ar' else (10 if language == 'en' else 0)
        title_text = ' '.join(_words(title))
        full_text = ' '.join(_words(text))
        subject_words = [w for w in _words(subject) if len(w) > 2 and w not in STOP_WORDS]
        lesson_words = _core_lesson_words(lesson_title)
        lesson_matches = sum(1 for w in lesson_words if w in full_text)
        subject_matches = sum(1 for w in subject_words if w in full_text)
        score += min(30, lesson_matches * 15)
        score += min(16, subject_matches * 8)
        if any(w in title_text for w in lesson_words):
            score += 10
        if grade and any(w in text for w in grade.replace('الصف', '').replace('الأساسي', '').split() if w):
            score += 5
        if 'شرح' in text or 'درس' in text or 'تعليم' in text:
            score += 4
        if any(dom in url for dom in KNOWN_EDUCATIONAL):
            score += 8
        if IMAGE_EXT_RE.search(url):
            score += 3
        score = max(10, min(99, score))
        return {
            'title': title[:280], 'url': url, 'resource_type': rtype, 'language': language,
            'source_name': source_name, 'description': description[:480], 'relevance_score': score, 'group': group,
        }

    @staticmethod
    def _detect_type(group, url, text):
        if group != 'general':
            return group if group in ('video', 'image', 'simulation', 'activity', 'experiment', 'reading') else 'link'
        low = url.lower()
        if 'youtube.com' in low or 'youtu.be' in low:
            return 'video'
        if IMAGE_EXT_RE.search(url):
            return 'image'
        if low.endswith('.pdf') or 'pdf' in low:
            return 'reading'
        if 'video' in text or 'فيديو' in text:
            return 'video'
        return 'article' if 'article' in text else 'link'

    @staticmethod
    def _source_name(url):
        host = urlparse(url).netloc.lower().replace('www.', '')
        if host.startswith('m.'):
            host = host[2:]
        known = {'youtube.com': 'يوتيوب', 'wikipedia.org': 'ويكيبيديا', 'khanacademy.org': 'أكاديمية خان'}
        return known.get(host, host)

    def deduplicate_by_domain(self, classified, cap=None):
        cap = cap or self.domain_cap
        by_domain = {}
        for item in sorted(classified, key=lambda x: x['relevance_score'], reverse=True):
            domain = urlparse(item['url']).netloc.lower().replace('www.', '')
            by_domain.setdefault(domain, []).append(item)
        out = []
        for domain, items in by_domain.items():
            out.extend(items[:cap])
        return out


class SearchUnavailable(Exception):
    """يُرمى عندما يفشل البحث أو لا توجد نتائج."""
