import hashlib
import ipaddress
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import requests
from django import template
from django.core.cache import cache

from school.public_models import SchoolPublicSettings

register = template.Library()

MAX_FEED_BYTES = 2 * 1024 * 1024
FEED_TIMEOUT = (3.05, 8)
FEED_CACHE_SECONDS = 15 * 60
NEGATIVE_CACHE_SECONDS = 30
MAX_REDIRECTS = 3


def _is_allowed_public_url(url):
    """Allow HTTPS public URLs and reject obvious local/private literal targets."""
    try:
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        host = parsed.hostname.strip().lower()
        if host in {'localhost', 'localhost.localdomain'} or host.endswith('.local'):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except Exception:
        return False


def _text(node, names):
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ''


def _parse_feed(data):
    root = ET.fromstring(data)
    items = []

    for item in root.findall('.//item')[:12]:
        title = _text(item, ['title'])
        link = _text(item, ['link'])
        if title and link and urlparse(link).scheme in ('http', 'https'):
            items.append({'title': title[:220], 'url': link})

    if not items:
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('.//a:entry', ns)[:12]:
            title = _text(entry, ['{http://www.w3.org/2005/Atom}title'])
            link = ''
            for link_node in entry.findall('{http://www.w3.org/2005/Atom}link'):
                href = (link_node.attrib.get('href') or '').strip()
                rel = (link_node.attrib.get('rel') or 'alternate').strip()
                if href and rel == 'alternate':
                    link = href
                    break
            if title and link and urlparse(link).scheme in ('http', 'https'):
                items.append({'title': title[:220], 'url': link})

    return items[:8]


def _download_feed(feed_url):
    """Fetch a feed with requests/certifi and manually validate HTTPS redirects."""
    current_url = feed_url
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8',
        'Accept-Language': 'ar,en;q=0.7',
        'Cache-Control': 'no-cache',
    }

    for _ in range(MAX_REDIRECTS + 1):
        if not _is_allowed_public_url(current_url):
            return b''

        response = requests.get(
            current_url,
            headers=headers,
            timeout=FEED_TIMEOUT,
            allow_redirects=False,
            stream=True,
        )

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get('Location', '').strip()
            response.close()
            if not location:
                return b''
            current_url = urljoin(current_url, location)
            continue

        response.raise_for_status()
        data = bytearray()
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                data.extend(chunk)
                if len(data) > MAX_FEED_BYTES:
                    return b''
        finally:
            response.close()
        return bytes(data)

    return b''


def _fetch_news(feed_url):
    if not feed_url or not _is_allowed_public_url(feed_url):
        return []

    digest = hashlib.sha256(feed_url.encode('utf-8')).hexdigest()[:24]
    cache_key = f'school-public-feed-v3:{digest}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        data = _download_feed(feed_url)
        items = _parse_feed(data) if data else []
    except (requests.RequestException, ET.ParseError, ValueError, OSError):
        items = []

    cache.set(
        cache_key,
        items,
        FEED_CACHE_SECONDS if items else NEGATIVE_CACHE_SECONDS,
    )
    return items


@register.simple_tag
def school_home_extras():
    try:
        settings = SchoolPublicSettings.objects.select_related('school_info').first()
    except Exception:
        return {'settings': None, 'news': [], 'whatsapp_number': ''}

    if not settings:
        return {'settings': None, 'news': [], 'whatsapp_number': ''}

    news = []
    if settings.news_enabled and settings.news_feed_url:
        news = _fetch_news(settings.news_feed_url)
        if not news:
            news = [{
                'title': 'تعذر تحميل الأخبار من المصدر حالياً — اضغط لفتح موجز الأخبار مباشرة',
                'url': settings.news_feed_url,
            }]

    raw_mobile = (settings.school_mobile or '').strip()
    whatsapp_number = ''
    if raw_mobile.startswith('+') or raw_mobile.startswith('00'):
        whatsapp_number = re.sub(r'\D', '', raw_mobile)
        if whatsapp_number.startswith('00'):
            whatsapp_number = whatsapp_number[2:]

    return {
        'settings': settings,
        'news': news,
        'whatsapp_number': whatsapp_number,
    }
