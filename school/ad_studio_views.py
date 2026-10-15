import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render


@login_required
def school_ad_studio(request):
    """Safe first-stage ad studio: preview only; no image API or Facebook publishing."""
    profile = getattr(request.user, "profile", None)
    if not (request.user.is_staff or getattr(profile, "role", "") == "admin"):
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
    return render(request, "school/ad_studio.html", defaults)
