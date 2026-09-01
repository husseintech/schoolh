from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import SchoolInfo
from .public_models import SchoolPublicSettings


@login_required
def school_info_view(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')

    info = SchoolInfo.objects.first()
    public_settings = None
    if info:
        public_settings, _ = SchoolPublicSettings.objects.get_or_create(school_info=info)

    if request.method == 'POST':
        name_ar = request.POST.get('name_ar', '').strip()
        name_en = request.POST.get('name_en', '').strip()
        principal_name = request.POST.get('principal_name', '').strip()
        national_number = request.POST.get('national_number', '').strip()
        latitude = request.POST.get('latitude', '').strip()
        longitude = request.POST.get('longitude', '').strip()

        try:
            lat_val = float(latitude) if latitude else None
            lon_val = float(longitude) if longitude else None
        except ValueError:
            messages.error(request, 'خطأ في تنسيق الإحداثيات، استخدم النقطة (.) كفاصل عشري')
            return redirect('school_info')

        if info:
            info.name_ar = name_ar
            info.name_en = name_en
            info.principal_name = principal_name
            info.national_number = national_number
            info.latitude = lat_val
            info.longitude = lon_val
            info.school_logo = request.POST.get('school_logo', '').strip()
            info.ministry_logo = request.POST.get('ministry_logo', '').strip()
            info.save()
        else:
            info = SchoolInfo.objects.create(
                name_ar=name_ar,
                name_en=name_en,
                principal_name=principal_name,
                national_number=national_number,
                latitude=lat_val,
                longitude=lon_val,
                school_logo=request.POST.get('school_logo', '').strip(),
                ministry_logo=request.POST.get('ministry_logo', '').strip(),
            )

        public_settings, _ = SchoolPublicSettings.objects.get_or_create(school_info=info)
        public_settings.school_mobile = request.POST.get('school_mobile', '').strip()
        public_settings.save(update_fields=['school_mobile', 'updated_at'])

        messages.success(request, 'تم حفظ بيانات المدرسة وإعدادات التواصل')
        return redirect('school_info')

    return render(request, 'school/school_info.html', {
        'info': info,
        'public_settings': public_settings,
    })
