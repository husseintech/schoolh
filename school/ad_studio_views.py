from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.conf import settings


@login_required
def school_ad_studio(request):
    """Safe first-stage ad studio: preview only; no image API or Facebook publishing."""
    try:
        profile = request.user.profile
    except Exception:
        profile = None
    if getattr(profile, "role", "") != "admin":
        return HttpResponseForbidden("ليس لديك صلاحية الوصول إلى استوديو الإعلانات.")
    defaults = {
        "kind": "تهنئة وتفوق",
        "title": "تهنئة للطلبة المتفوقين",
        "body": "تبارك مدرسة المنصور الأساسية لطلبتها المتفوقين، وتتمنى لهم مزيدًا من النجاح والتميز.",
        "palette": "blue",
    }
    if request.method == "POST":
        defaults["kind"] = request.POST.get("kind", defaults["kind"])[:80]
        defaults["title"] = request.POST.get("title", defaults["title"])[:160]
        defaults["body"] = request.POST.get("body", defaults["body"])[:1200]
        defaults["palette"] = request.POST.get("palette", "blue")
    defaults["meta_pages"] = [
        {"id": page.get("id"), "name": page.get("name")}
        for page in request.session.get("meta_pages", [])
        if page.get("id") and page.get("name")
    ]
    defaults["meta_selected_page"] = request.session.get("meta_selected_page", {})
    defaults["meta_configured"] = bool(
        getattr(settings, "META_APP_ID", "")
        and getattr(settings, "META_APP_SECRET", "")
        and getattr(settings, "META_OAUTH_REDIRECT_URI", "")
    )
    return render(request, "school/ad_studio.html", defaults)
