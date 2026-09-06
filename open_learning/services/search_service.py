"""محرك البحث عن المصادر التعليمية.

روابط حقيقية فقط من نتائج البحث الفعلية، مع حاجز ملاءمة إلزامي قبل إرجاع
أي نتيجة إلى طبقة الحفظ. المحرك مجاني افتراضياً عبر DuckDuckGo.
"""
import os
import re
import time
import html
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
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
    value = re.sub(r'[\u064b-\u065f\u0670ـ]', '', value or '')
    value = re.sub('[أإآ]', 'ا', value).replace('ى', 'ي')
    return [w[2:] if w.startswith('ال') and len(w) > 4 else w
            for w in TITLE_FILLERS.sub(' ', value).lower().split() if w]


def _core_lesson_words(value):
    stop = set(_words(' '.join(STOP_WORDS)))
    return [w for w in _words(value) if len(w) > 2 and w not in stop]


class SearchResultParser(HTMLParser):
    """DuckDuckGo anchors do not guarantee attribute order or quote style."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.current = None
        self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        if tag == 'a' and 'result__a' in classes:
            self.current = {'url': attrs.get('href', ''), 'title': '', 'snippet': ''}
            self.items.append(self.current)
            self.capture = ('title', tag)
        elif 'result__snippet' in classes and self.current is not None:
            self.capture = ('snippet', tag)

    def handle_data(self, text):
        if self.capture and self.current is not None:
            self.current[self.capture[0]] += text

    def handle_endtag(self, tag):
        if self.capture and tag == self.capture[1]:
            self.capture = None


class SearchService:
    def __init__(self):
        self.provider = os.getenv('SEARCH_PROVIDER', 'duckduckgo').strip().lower()
        self.google_cse_id = os.getenv('GOOGLE_CSE_ID', '').strip()
        self.google_api_key = os.getenv('GOOGLE_CSE_API_KEY', '').strip()
        self.domain_cap = int(os.getenv('SEARCH_DOMAIN_CAP', '2'))

    def search_all(self, lesson_title, grade, subject, max_per_group=4):
        """بحث متعدد، ثم رفض أي نتيجة لا تشير فعلاً إلى موضوع الدرس."""
        results = []
        seen_urls = set()
        # Three complementary queries run together instead of eight serial requests.
        specs = [QUERY_TEMPLATES[i] for i in (0, 2, 7)]
        def fetch(spec):
            query = spec['query'].format(title=lesson_title, grade=grade, subject=subject)
            try:
                return spec, self._search(query, limit=max_per_group), None
            except SearchUnavailable:
                return spec, [], 'unavailable'
        with ThreadPoolExecutor(max_workers=3) as executor:
            batches = list(executor.map(fetch, specs))
        if all(error for _, _, error in batches):
            raise SearchUnavailable('تعذر الوصول إلى محرك المصادر أو حجب الطلبات. حاول لاحقًا؛ يمكن لمدير النظام إعداد محرك بحث بديل.')
        for spec, raw, error in batches:
            group = spec['group']
            for item in raw:
                norm = normalize_url(item['url'])
                if not norm or norm in seen_urls:
                    continue
                item['group'] = group
                if not self.is_relevant(item, lesson_title, subject):
                    continue
                seen_urls.add(norm)
                results.append(item)
        return results

    def _search(self, query, limit):
        if self.provider == 'google':
            if not self.google_cse_id or not self.google_api_key:
                raise SearchUnavailable('محرك البحث غير مهيأ.')
            return self._search_google(query, limit)
        return self._search_duckduckgo(query, limit)

    def _search_duckduckgo(self, query, limit):
        url = 'https://html.duckduckgo.com/html/'
        try:
            resp = requests.get(url, params={'q': query}, headers={'User-Agent': USER_AGENT}, timeout=(3, 8))
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise SearchUnavailable('تعذر الاتصال بمحرك البحث.') from exc
        page = resp.text
        if resp.status_code == 202 or 'anomaly.js' in page or 'anomaly-modal' in page:
            raise SearchUnavailable('محرك البحث يطلب تحققًا بشريًا؛ لم يُنفذ البحث.')
        parser = SearchResultParser()
        parser.feed(page)
        items = []
        for item in parser.items:
            real_url = self._extract_duckduckgo_url(item['url'])
            if not real_url or not real_url.startswith('http'):
                continue
            title = re.sub(r'\s+', ' ', item['title']).strip()
            snippet = re.sub(r'\s+', ' ', item['snippet']).strip()
            if title and real_url.startswith(('https://', 'http://')):
                items.append({'title': title, 'url': real_url, 'snippet': snippet})
            if len(items) >= limit:
                break
        if not items and 'no-results' not in page:
            raise SearchUnavailable('تعذر قراءة نتائج محرك البحث.')
        return items

    @staticmethod
    def _extract_duckduckgo_url(href):
        href = html.unescape(href)
        if href.startswith(('/l/', '//duckduckgo.com/l/', 'https://duckduckgo.com/l/')):
            qs = parse_qs(urlparse(href).query)
            if 'uddg' in qs:
                return qs['uddg'][0]
        if href.startswith('http'):
            return href
        return None

    def _search_google(self, query, limit):
        url = 'https://www.googleapis.com/customsearch/v1'
        params = {
            'key': self.google_api_key,
            'cx': self.google_cse_id,
            'q': query,
            'num': min(limit, 10),
            'hl': 'ar',
        }
        try:
            resp = requests.get(url, params=params, timeout=(3, 8))
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise SearchUnavailable('تعذر الاتصال بمحرك البحث المهيأ؛ راجع إعداداته وحد الاستخدام.') from exc
        items = []
        for item in data.get('items', []):
            items.append({
                'title': item.get('title', ''),
                'url': item.get('link', ''),
                'snippet': re.sub(r'\s+', ' ', item.get('snippet', '')).strip(),
            })
        return items

    def validate_url(self, url):
        import ipaddress
        import socket
        try:
            parsed = urlparse(url)
            if not normalize_url(url) or parsed.port not in (None, 80, 443):
                return False
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                return False
            # Never follow an untrusted search result's redirects on the server.
            with requests.head(url, headers={'User-Agent': USER_AGENT}, timeout=(2, 3), allow_redirects=False) as resp:
                return 200 <= resp.status_code < 400 or resp.status_code in (403, 405)
        except (requests.RequestException, OSError, ValueError):
            return False

    def is_relevant(self, item, lesson_title, subject=''):
        """يشترط ظهور كلمة دلالية من موضوع الدرس في عنوان النتيجة أو وصفها."""
        haystack = ' '.join(_words((item.get('title') or '') + ' ' + (item.get('snippet') or '')))
        lesson_terms = _core_lesson_words(lesson_title)
        subject_terms = [w for w in _words(subject) if len(w) > 2 and w not in STOP_WORDS]
        if lesson_terms:
            return sum(term in haystack for term in lesson_terms) / len(lesson_terms) >= 0.5
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
        full_text = ' '.join(_words(text))
        title_text = ' '.join(_words(title))
        subject_words = [w for w in _words(subject) if len(w) > 2 and w not in STOP_WORDS]
        lesson_words = _core_lesson_words(lesson_title)
        score += min(30, sum(1 for w in lesson_words if w in full_text) * 15)
        score += min(16, sum(1 for w in subject_words if w in full_text) * 8)
        if any(w in title_text for w in lesson_words):
            score += 10
        if grade and any(w in text for w in grade.replace('الصف', '').replace('الأساسي', '').split() if w):
            score += 5
        if 'شرح' in text or 'درس' in text or 'تعليم' in text:
            score += 4
        host = urlparse(url).hostname or ''
        if any(host == dom or host.endswith('.' + dom) for dom in KNOWN_EDUCATIONAL):
            score += 8
        if IMAGE_EXT_RE.search(url):
            score += 3
        score = max(10, min(99, score))
        return {
            'title': title[:280],
            'url': url,
            'resource_type': rtype,
            'language': language,
            'source_name': source_name,
            'description': description[:480],
            'relevance_score': score,
            'group': group,
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
        return 'reading' if 'article' in text else 'link'

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
