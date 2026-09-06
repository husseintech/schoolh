"""Public Wikimedia search APIs and clearly labelled teacher search shortcuts."""
import html
import re
from urllib.parse import urlencode

import requests
from django.core.cache import cache


CATALOGS = (
    ('ar.wikipedia.org', 'ويكيبيديا العربية', 0, 'reading'),
    ('ar.wikibooks.org', 'ويكي الكتب العربية', 0, 'reading'),
    ('commons.wikimedia.org', 'ويكيميديا كومنز', 6, 'image'),
)
USER_AGENT = 'SchoolhLearningSources/1.0 (https://schoolhh.vercel.app/)'


class CatalogUnavailable(Exception):
    pass


def catalog_search(host, name, namespace, kind, title, limit=4):
    import hashlib
    # Hosts come only from the fixed catalog, never user input or search results.
    if host not in {catalog[0] for catalog in CATALOGS}:
        raise CatalogUnavailable('مكتبة غير معروفة')
    query = re.sub(r'[^\w\s\u0600-\u06ff]', ' ', title).strip()[:200]
    if not query:
        return []
    key = 'open-sources-v1:' + hashlib.sha256(f'{host}:{query}:{limit}'.encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        response = requests.get(
            f'https://{host}/w/api.php',
            params={'action': 'query', 'list': 'search', 'srsearch': query,
                    'srnamespace': namespace, 'srlimit': limit, 'format': 'json', 'formatversion': 2},
            headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'},
            timeout=(3, 6), allow_redirects=False,
        )
        if response.status_code != 200:
            raise CatalogUnavailable(f'تعذر الاتصال بـ{name}')
        data = response.json()
        if not isinstance(data, dict) or 'error' in data:
            raise CatalogUnavailable(f'تعذر البحث في {name}')
        rows = data.get('query', {}).get('search')
        if not isinstance(rows, list):
            raise CatalogUnavailable(f'استجابة غير مكتملة من {name}')
    except (requests.RequestException, ValueError, AttributeError) as exc:
        raise CatalogUnavailable(f'تعذر الاتصال بـ{name}') from exc
    results = []
    for row in rows[:limit]:
        if not isinstance(row, dict) or type(row.get('pageid')) is not int or row['pageid'] <= 0:
            continue
        raw_title = row.get('title')
        if not isinstance(raw_title, str) or not raw_title.strip():
            continue
        snippet = row.get('snippet') if isinstance(row.get('snippet'), str) else ''
        snippet = html.unescape(re.sub(r'<[^>]*>', '', snippet))
        result_kind = kind
        if kind == 'image' and not re.search(r'\.(png|jpe?g|svg|gif|webp|tiff?)$', raw_title, re.I):
            result_kind = 'link'
        results.append({
            'title': raw_title, 'url': f'https://{host}/?curid={row["pageid"]}',
            'snippet': snippet, 'group': result_kind, 'catalog_name': name,
            'catalog_reference': True,
        })
    cache.set(key, results, timeout=600)
    return results


def teacher_search_links(lesson):
    """These are search pages, not discovered or verified teaching resources."""
    brief = (lesson.ai_payload or {}).get('_brief', {})
    grade = f'الصف {brief["grade"]}' if brief.get('grade') else ' '.join(lesson.student_classes.values_list('name', flat=True))
    subject = lesson.subject.name if lesson.subject else ''
    topic = ' '.join(filter(None, (lesson.title[:100], subject[:40], grade[:40], brief.get('focus', '')[:100])))
    links = [
        {'title': 'فيديو يشرح الدرس', 'description': 'بحث في يوتيوب بعنوان الدرس والصف؛ شاهد الفيديو قبل إضافته.',
         'url': 'https://www.youtube.com/results?' + urlencode({'search_query': topic + ' شرح'}), 'icon': 'bi-play-circle'},
        {'title': 'أوراق عمل وتطبيقات', 'description': 'بحث موجّه في Google؛ راجع الإجابات ومصدر الورقة وحقوق استخدامها.',
         'url': 'https://www.google.com/search?' + urlencode({'q': topic + ' ورقة عمل filetype:pdf'}), 'icon': 'bi-file-earmark-text'},
        {'title': 'شرح في أكاديمية خان', 'description': 'بحث داخل نطاق أكاديمية خان؛ قد لا تتوفر نتائج عربية لكل درس.',
         'url': 'https://www.google.com/search?' + urlencode({'q': f'site:khanacademy.org {lesson.title} {subject}'}), 'icon': 'bi-book'},
    ]
    if any(term in subject for term in ('علوم', 'فيزياء', 'كيمياء', 'رياضيات', 'أحياء')):
        links.append({'title': 'محاكاة في PhET', 'description': 'بحث داخل نطاق PhET عن محاكاة للمفهوم؛ تحقق من مستوى المحاكاة.',
                      'url': 'https://www.google.com/search?' + urlencode({'q': f'site:phet.colorado.edu {lesson.title}'}), 'icon': 'bi-diagram-3'})
    return links
