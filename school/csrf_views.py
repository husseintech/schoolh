from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _safe_retry_url(request):
    referer = request.META.get('HTTP_REFERER', '')
    if referer and url_has_allowed_host_and_scheme(
        referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        retry_url = referer
    else:
        retry_url = reverse('home')
    parts = urlsplit(retry_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query['csrf_refreshed'] = '1'
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _forget_expired_csrf_cookie(response):
    response.delete_cookie(
        settings.CSRF_COOKIE_NAME,
        path=settings.CSRF_COOKIE_PATH,
        domain=settings.CSRF_COOKIE_DOMAIN,
        samesite=settings.CSRF_COOKIE_SAMESITE,
    )
    add_never_cache_headers(response)
    return response


def csrf_failure(request, reason=''):
    """Recover safely from an expired token without exposing Django's 403 page."""
    is_json = (
        request.content_type == 'application/json'
        or 'application/json' in request.headers.get('Accept', '')
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    )
    if is_json:
        return _forget_expired_csrf_cookie(JsonResponse({
            'error': 'انتهت جلسة الحماية. حدّث الصفحة ثم أعد المحاولة؛ لم يتم تنفيذ الطلب.',
            'csrf_expired': True,
        }, status=403))

    return _forget_expired_csrf_cookie(redirect(_safe_retry_url(request)))
