import base64
from urllib.parse import quote

import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST


@login_required
@require_POST
def generate_ad_background(request):
    """Use a no-key image generation service; availability and rate limits depend on the provider."""
    try:
        if request.user.profile.role != "admin":
            return HttpResponseForbidden("هذه العملية متاحة لمسؤول المدرسة فقط.")
    except Exception:
        return HttpResponseForbidden("هذه العملية متاحة لمسؤول المدرسة فقط.")

    kind = request.POST.get("kind", "إعلان مدرسي").strip()[:80]
    palette = (
        "light sky blue, white and restrained gold accents"
        if request.POST.get("palette") == "light"
        else "formal deep navy blue, royal blue and restrained gold accents"
    )
    prompt = (
        "Premium portrait 2:3 background artwork for a public elementary school's social media announcement. "
        f"Theme: {kind}. Palette: {palette}. Elegant subtle arabesque geometry and small educational motifs "
        "near outer edges, generous calm central space for Arabic text to be overlaid later. "
        "No text, letters, numbers, logos, watermarks, or people. Clean professional graphic design."
    )
    try:
        # No personal API key is required by this third-party endpoint at the time of implementation.
        url = "https://image.pollinations.ai/prompt/" + quote(prompt, safe="")
        response = requests.get(
            url,
            params={"width": 1024, "height": 1536, "model": "flux", "nologo": "true", "safe": "true"},
            headers={"Accept": "image/png,image/jpeg,image/webp"},
            timeout=(10, 85),
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
        if content_type not in ("image/png", "image/jpeg", "image/webp"):
            return JsonResponse({"ok": False, "error": "لم تُرجع خدمة الصور ملف صورة صالحًا. جرّب مرة أخرى."}, status=502)
        image_bytes = response.content
        if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
            return JsonResponse({"ok": False, "error": "حجم الصورة الناتجة غير مناسب. حاول مرة أخرى."}, status=502)
        signature_ok = (
            (content_type == "image/png" and image_bytes.startswith(bytes.fromhex("89504e470d0a1a0a")))
            or (content_type == "image/jpeg" and image_bytes.startswith(bytes.fromhex("ffd8ff")))
            or (content_type == "image/webp" and len(image_bytes) > 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP")
        )
        if not signature_ok:
            return JsonResponse({"ok": False, "error": "تعذر التحقق من ملف الصورة الناتج."}, status=502)
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        return JsonResponse({"ok": True, "image_data": f"data:{content_type};base64,{image_b64}"})
    except requests.Timeout:
        return JsonResponse({"ok": False, "error": "تأخر توليد الصورة. جرّب مرة أخرى بعد قليل."}, status=504)
    except requests.RequestException:
        return JsonResponse({"ok": False, "error": "خدمة التوليد المجانية غير متاحة الآن أو وصلت إلى حد الاستخدام. حاول لاحقًا."}, status=502)
