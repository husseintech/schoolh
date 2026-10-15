import base64
import binascii
import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST


GRAPH_VERSION = getattr(settings, "META_GRAPH_API_VERSION", "v23.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _is_school_admin(user):
    try:
        return user.is_authenticated and user.profile.role == "admin"
    except Exception:
        return False


@login_required
@require_GET
def facebook_connect(request):
    """Start Meta OAuth; state is session-bound and publishing is not performed here."""
    if not _is_school_admin(request.user):
        return HttpResponseForbidden("هذه العملية متاحة لمسؤول المدرسة فقط.")
    app_id = getattr(settings, "META_APP_ID", "")
    redirect_uri = getattr(settings, "META_OAUTH_REDIRECT_URI", "")
    if not app_id or not redirect_uri:
        messages.error(request, "يلزم إعداد META_APP_ID و META_OAUTH_REDIRECT_URI في متغيرات البيئة أولًا.")
        return redirect("school_ad_studio")
    state = secrets.token_urlsafe(32)
    request.session["meta_oauth_state"] = state
    request.session["meta_oauth_user_id"] = request.user.pk
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": "pages_show_list,pages_read_engagement,pages_manage_posts",
    }
    return redirect("https://www.facebook.com/" + GRAPH_VERSION + "/dialog/oauth?" + urlencode(params))


@login_required
@require_GET
def facebook_callback(request):
    if not _is_school_admin(request.user):
        return HttpResponseForbidden("هذه العملية متاحة لمسؤول المدرسة فقط.")
    expected_state = request.session.pop("meta_oauth_state", None)
    expected_user = request.session.pop("meta_oauth_user_id", None)
    received_state = request.GET.get("state")
    if not expected_state or not received_state or not secrets.compare_digest(expected_state, received_state) or expected_user != request.user.pk:
        messages.error(request, "تعذر التحقق من طلب الربط. أعد المحاولة من داخل استوديو الإعلانات.")
        return redirect("school_ad_studio")
    if request.GET.get("error"):
        messages.error(request, "لم يكتمل تفويض فيسبوك. يمكنك إعادة المحاولة متى شئت.")
        return redirect("school_ad_studio")
    code = request.GET.get("code")
    app_id = getattr(settings, "META_APP_ID", "")
    app_secret = getattr(settings, "META_APP_SECRET", "")
    redirect_uri = getattr(settings, "META_OAUTH_REDIRECT_URI", "")
    if not all([code, app_id, app_secret, redirect_uri]):
        messages.error(request, "إعدادات Meta غير مكتملة. تحقق من متغيرات البيئة دون إرسال الأسرار لأي شخص.")
        return redirect("school_ad_studio")
    try:
        response = requests.get(
            f"{GRAPH_BASE}/oauth/access_token",
            params={"client_id": app_id, "client_secret": app_secret, "redirect_uri": redirect_uri, "code": code},
            timeout=15,
        )
        response.raise_for_status()
        token_data = response.json()
        user_token = token_data.get("access_token")
        if not user_token:
            raise ValueError("Missing access token")
        pages_response = requests.get(
            f"{GRAPH_BASE}/me/accounts",
            params={"access_token": user_token, "fields": "id,name,access_token,tasks"},
            timeout=15,
        )
        pages_response.raise_for_status()
        pages = pages_response.json().get("data", [])
        # Keep tokens only in the server-side Django session; never render tokens to HTML.
        request.session["meta_user_access_token"] = user_token
        request.session["meta_pages"] = [
            {"id": p.get("id"), "name": p.get("name"), "access_token": p.get("access_token")}
            for p in pages if p.get("id") and p.get("name") and p.get("access_token")
        ]
        request.session.pop("meta_selected_page", None)
        messages.success(request, "تم التفويض. اختر صفحة المدرسة من القائمة داخل الاستوديو.")
    except (requests.RequestException, ValueError, KeyError):
        request.session.pop("meta_user_access_token", None)
        request.session.pop("meta_pages", None)
        messages.error(request, "تعذر إكمال الاتصال بـ Meta. تحقق من إعداد التطبيق والصلاحيات ثم أعد المحاولة.")
    return redirect("school_ad_studio")


@login_required
@require_POST
def facebook_select_page(request):
    if not _is_school_admin(request.user):
        return HttpResponseForbidden("هذه العملية متاحة لمسؤول المدرسة فقط.")
    pages = request.session.get("meta_pages", [])
    selected_id = request.POST.get("page_id", "")
    selected = next((p for p in pages if str(p.get("id")) == selected_id and p.get("access_token")), None)
    if not selected:
        messages.error(request, "لم يتم العثور على الصفحة ضمن الصفحات التي وافقت على ربطها.")
        return redirect("school_ad_studio")
    request.session["meta_selected_page"] = {
        "id": selected["id"],
        "name": selected["name"],
        "access_token": selected["access_token"],
    }
    messages.success(request, f"تم اختيار صفحة «{selected['name']}». النشر الفعلي يبقى معطلًا حتى تجهيز صورة الإعلان واختبار الصلاحيات.")
    return redirect("school_ad_studio")


@login_required
@require_POST
def facebook_disconnect(request):
    if not _is_school_admin(request.user):
        return HttpResponseForbidden("هذه العملية متاحة لمسؤول المدرسة فقط.")
    for key in ("meta_oauth_state", "meta_oauth_user_id", "meta_user_access_token", "meta_pages", "meta_selected_page"):
        request.session.pop(key, None)
    messages.success(request, "تم فصل الربط المحلي وحذف الرموز من الجلسة الحالية.")
    return redirect("school_ad_studio")


@login_required
@require_POST
def facebook_publish_announcement(request):
    """Publish a user-confirmed PNG only when the deployment explicitly enables it."""
    if not _is_school_admin(request.user):
        return HttpResponseForbidden("هذه العملية متاحة لمسؤول المدرسة فقط.")
    if not getattr(settings, "META_PUBLISH_ENABLED", False):
        messages.error(request, "النشر المباشر غير مفعّل بعد. فعّله فقط بعد اختبار الربط والصلاحيات.")
        return redirect("school_ad_studio")
    page = request.session.get("meta_selected_page") or {}
    page_id, page_token = page.get("id"), page.get("access_token")
    if not page_id or not page_token:
        messages.error(request, "اربط صفحة المدرسة واخترها أولًا.")
        return redirect("school_ad_studio")
    if request.POST.get("confirm_publish") != "yes":
        messages.error(request, "لم يتم النشر لأن التأكيد الصريح غير موجود.")
        return redirect("school_ad_studio")
    data_url = request.POST.get("image_data", "")
    prefix = "data:image/png;base64,"
    if not data_url.startswith(prefix):
        messages.error(request, "تعذر قراءة صورة الإعلان. أنشئ المعاينة مجددًا ثم حاول.")
        return redirect("school_ad_studio")
    try:
        image_bytes = base64.b64decode(data_url[len(prefix):], validate=True)
    except (binascii.Error, ValueError):
        messages.error(request, "صيغة صورة الإعلان غير صحيحة.")
        return redirect("school_ad_studio")
    # Keep requests bounded to protect the serverless function and avoid oversized uploads.
    if not image_bytes or len(image_bytes) > 8 * 1024 * 1024 or not image_bytes.startswith(b"\\x89PNG\\r\\n\\x1a\\n"):
        messages.error(request, "حجم الصورة غير مناسب أو أن الملف ليس PNG صالحًا (الحد 8 ميغابايت).")
        return redirect("school_ad_studio")
    message = request.POST.get("message", "").strip()[:2000]
    if not message:
        messages.error(request, "أدخل نص المنشور قبل النشر.")
        return redirect("school_ad_studio")
    try:
        response = requests.post(
            f"{GRAPH_BASE}/{page_id}/photos",
            data={"access_token": page_token, "message": message, "published": "true"},
            files={"source": ("school-announcement.png", image_bytes, "image/png")},
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("id"):
            raise ValueError("Meta response did not contain a photo id")
        messages.success(request, f"أُرسل الإعلان إلى صفحة «{page.get('name', 'المدرسة')}» بنجاح. معرّف الصورة: {result['id']}")
    except (requests.RequestException, ValueError):
        # Never log or expose the page access token in the user-facing error.
        messages.error(request, "لم يؤكد Meta نجاح النشر. لم نعرض بيانات الاتصال الحساسة؛ راجع صلاحيات التطبيق وسجل Meta ثم أعد المحاولة عند الحاجة.")
    return redirect("school_ad_studio")
