import ipaddress
import re
import socket
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django import template
from django.core.cache import cache

from school.public_models import SchoolPublicSettings

register = template.Library()

MAX_FEED_BYTES = 512 * 1024
FEED_TIMEOUT_SECONDS = 3
FEED_CACHE_SECONDS = 15 * 60


def _is_public_https_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname:
            return False
        # Reject literal private/reserved IP hosts.
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            return ip.is_global
        except ValueError:
            pass
        # Resolve host and reject any private/reserved destination.
        for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
            address = ipaddress.ip_address(item[4][0])
            if not address.is_global:
                return False
        return True
    except Exception:
        return False


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        if not _is_public_https_url(target):
            raise ValueError('Unsafe redirect target')
        return super().redirect_request(req, fp, code, msg, headers, target)


def _text(node, names):
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ''


def _parse_feed(data):
    root = ET.fromstring(data)
    items = []

    # RSS 2.x
    for item in root.findall('.//item')[:8]:
        title = _text(item, ['title'])
        link = _text(item, ['link'])
        if title and link and urlparse(link).scheme in ('http', 'https'):
            items.append({'title': title[:220], 'url': link})

    # Atom
    if not items:
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('.//a:entry', ns)[:8]:
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

    return items[:6]


def _fetch_news(feed_url):
    if not feed_url or not _is_public_https_url(feed_url):
        return []
    cache_key = 'school-public-feed:' + str(abs(hash(feed_url)))
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        opener = build_opener(_SafeRedirectHandler())
        request = Request(feed_url, headers={'User-Agent': 'SchoolPortal/1.0 (+RSS reader)'})
        with opener.open(request, timeout=FEED_TIMEOUT_SECONDS) as response:
            content_type = (response.headers.get('Content-Type') or '').lower()
            if not any(kind in content_type for kind in ('xml', 'rss', 'atom', 'text/plain', 'application/octet-stream')):
                cache.set(cache_key, [], FEED_CACHE_SECONDS)
                return []
            data = response.read(MAX_FEED_BYTES + 1)
            if len(data) > MAX_FEED_BYTES:
                cache.set(cache_key, [], FEED_CACHE_SECONDS)
                return []
        items = _parse_feed(data)
    except Exception:
        items = []

    cache.set(cache_key, items, FEED_CACHE_SECONDS)
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
