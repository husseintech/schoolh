import base64
import os
import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST

@login_required
@require_POST
def generate_ad_background(request):
    try:
        if request.user.profile.role != "admin":
            return HttpResponseForbidden("هذه العملية متاحة لمسؤول المدرسة فقط.")
    except Exception:
        return HttpResponseForbidden("هذه العملية متاحة لمسؤول المدرسة فقط.")
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return JsonResponse({"ok": False, "error": "أضف OPENAI_API_KEY إلى متغيرات البيئة في الاستضافة لتفعيل توليد الصور."}, status=503)
    kind = request.POST.get("kind", "إعلان مدرسي").strip()[:80]
    palette = "light blue, white and restrained gold" if request.POST.get("palette") == "light" else "navy blue, royal blue and restrained gold"
    prompt = ("Create a premium portrait 2:3 background for a public elementary school social media announcement. Theme: " + kind +
      ". Palette: " + palette + ". Elegant subtle arabesque geometry and tiny educational motifs near outer edges. Keep center uncluttered for Arabic text overlay. No text, letters, numbers, logos, watermark or people. Professional clean graphic design.")
    try:
        response = requests.post("https://api.openai.com/v1/images/generations",
          headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
          json={"model":"gpt-image-1","prompt":prompt,"size":"1024x1536","quality":"medium","output_format":"png"},
          timeout=(10,90))
        response.raise_for_status()
        image_b64 = (response.json().get("data") or [{}])[0].get("b64_json")
        if not image_b64:
            return JsonResponse({"ok":False,"error":"لم تُرجع خدمة الصور ملفًا صالحًا."}, status=502)
        raw = base64.b64decode(image_b64, validate=True)
        if not raw.startswith(bytes.fromhex("89504e470d0a1a0a")):
            return JsonResponse({"ok":False,"error":"صيغة الصورة الناتجة غير صالحة."}, status=502)
        return JsonResponse({"ok":True,"image_data":"data:image/png;base64,"+image_b64})
    except requests.Timeout:
        return JsonResponse({"ok":False,"error":"استغرق توليد الصورة وقتًا طويلًا. حاول مجددًا."}, status=504)
    except requests.RequestException:
        return JsonResponse({"ok":False,"error":"تعذر توليد الصورة. تحقق من مفتاح الخدمة ورصيد API."}, status=502)
    except (ValueError, TypeError):
        return JsonResponse({"ok":False,"error":"وصل رد غير متوقع من خدمة الصور."}, status=502)
