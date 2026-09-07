import mimetypes
from datetime import date
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import escape_uri_path
from school.models import has_perm

from .google_drive import GoogleDriveService
from .models import SchoolRadioEntry, SchoolRadioFile
from .radio_forms import SchoolRadioEntryForm
from .services.ai_service import AIServiceUnavailable, get_provider
from .services.usage import log_usage


RADIO_FOLDER_NAME = 'ملف الإذاعة المدرسية'
MAX_FILES_PER_REQUEST = 10
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.pdf'}
ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif', 'application/pdf',
}


def _radio_permission_required(request, action):
    if has_perm(request.user, 'school_radio', action):
        return None
    messages.error(request, 'ليس لديك صلاحية لتنفيذ هذا الإجراء في ملف الإذاعة المدرسية')
    return redirect('home')


def _entry_queryset():
    return SchoolRadioEntry.objects.prefetch_related('presenters', 'participants', 'files')


def _iso_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _file_mimetype(uploaded):
    supplied = (uploaded.content_type or '').lower().split(';', 1)[0]
    guessed = (mimetypes.guess_type(uploaded.name)[0] or '').lower()
    return supplied if supplied in ALLOWED_MIME_TYPES else guessed


def _upload_files(request, entry):
    uploads = request.FILES.getlist('files')
    if not uploads:
        return 0
    if len(uploads) > MAX_FILES_PER_REQUEST:
        messages.error(request, f'يمكن رفع {MAX_FILES_PER_REQUEST} ملفات كحد أقصى في المرة الواحدة')
        uploads = uploads[:MAX_FILES_PER_REQUEST]

    service = GoogleDriveService()
    if not service.is_connected():
        messages.error(request, 'تم حفظ سجل الإذاعة، لكن يلزم ربط Google Drive قبل رفع الصور والملفات')
        return 0

    last_order = entry.files.aggregate(value=Max('order'))['value']
    order = 0 if last_order is None else last_order + 1
    saved = 0
    folder_path = [RADIO_FOLDER_NAME, entry.event_date.isoformat()]
    for uploaded in uploads:
        extension = Path(uploaded.name).suffix.lower()
        mimetype = _file_mimetype(uploaded)
        if extension not in ALLOWED_EXTENSIONS or mimetype not in ALLOWED_MIME_TYPES:
            messages.error(request, f'الملف «{uploaded.name}» غير مدعوم؛ المسموح صور JPG/PNG/WebP/HEIC أو PDF')
            continue
        if uploaded.size > MAX_FILE_SIZE:
            messages.error(request, f'الملف «{uploaded.name}» أكبر من 10 ميغابايت')
            continue
        try:
            data = uploaded.read()
            if not data:
                continue
            result = service.upload_to_folder_path(uploaded.name, data, mimetype, folder_path)
            SchoolRadioFile.objects.create(
                entry=entry,
                file_name=uploaded.name,
                file_type=result.get('mimeType') or mimetype,
                file_size=int(result.get('size') or uploaded.size or 0) or None,
                google_drive_file_id=result.get('id', ''),
                google_drive_url=result.get('webViewLink', ''),
                order=order,
            )
            order += 1
            saved += 1
        except Exception:
            messages.error(request, f'تعذّر رفع الملف «{uploaded.name}» إلى Google Drive؛ حاول رفعه مرة أخرى')
    return saved


@login_required
def school_radio_list(request):
    denied = _radio_permission_required(request, 'view')
    if denied:
        return denied
    entries = _entry_queryset()
    query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    if query:
        entries = entries.filter(
            Q(title__icontains=query) | Q(topic__icontains=query)
            | Q(presenters__full_name__icontains=query) | Q(participants__full_name__icontains=query)
            | Q(additional_presenters__icontains=query) | Q(additional_participants__icontains=query)
        ).distinct()
    parsed_from = _iso_date(date_from)
    parsed_to = _iso_date(date_to)
    if parsed_from:
        entries = entries.filter(event_date__gte=parsed_from)
    if parsed_to:
        entries = entries.filter(event_date__lte=parsed_to)
    return render(request, 'open_learning/radio_list.html', {
        'entries': entries,
        'filters': {'q': query, 'date_from': date_from, 'date_to': date_to},
        'gdrive_connected': GoogleDriveService().is_connected(),
    })


@login_required
def school_radio_add(request):
    denied = _radio_permission_required(request, 'add')
    if denied:
        return denied
    form = SchoolRadioEntryForm(
        request.POST or None,
        initial={'event_date': timezone.localdate(), 'title': 'الإذاعة المدرسية'},
    )
    if request.method == 'POST' and form.is_valid():
        entry = form.save(commit=False)
        entry.created_by = request.user
        entry.save()
        form.save_m2m()
        saved = _upload_files(request, entry)
        if saved:
            messages.success(request, f'تم إنشاء سجل الإذاعة ورفع {saved} ملفًا إلى Google Drive')
        else:
            messages.success(request, 'تم إنشاء سجل الإذاعة المدرسية')
        return redirect('ol_school_radio_detail', entry_id=entry.pk)
    return render(request, 'open_learning/radio_form.html', {
        'form': form, 'entry': None, 'gdrive_connected': GoogleDriveService().is_connected(),
    })


@login_required
def school_radio_edit(request, entry_id):
    denied = _radio_permission_required(request, 'edit')
    if denied:
        return denied
    entry = get_object_or_404(SchoolRadioEntry, pk=entry_id)
    original_topic = entry.topic
    form = SchoolRadioEntryForm(request.POST or None, instance=entry)
    if request.method == 'POST' and form.is_valid():
        entry = form.save(commit=False)
        if original_topic != entry.topic and (entry.ai_word or entry.ai_program):
            entry.ai_status = 'pending'
            entry.ai_reviewed_by = None
        entry.save()
        form.save_m2m()
        saved = _upload_files(request, entry)
        message = 'تم تحديث بيانات الإذاعة المدرسية'
        if saved:
            message += f' ورفع {saved} ملفًا جديدًا'
        messages.success(request, message)
        return redirect('ol_school_radio_detail', entry_id=entry.pk)
    return render(request, 'open_learning/radio_form.html', {
        'form': form, 'entry': entry, 'gdrive_connected': GoogleDriveService().is_connected(),
    })


@login_required
def school_radio_detail(request, entry_id):
    denied = _radio_permission_required(request, 'view')
    if denied:
        return denied
    entry = get_object_or_404(_entry_queryset(), pk=entry_id)
    return render(request, 'open_learning/radio_detail.html', {
        'entry': entry,
        'gdrive_connected': GoogleDriveService().is_connected(),
    })


@login_required
def school_radio_add_files(request, entry_id):
    denied = _radio_permission_required(request, 'edit')
    if denied:
        return denied
    entry = get_object_or_404(SchoolRadioEntry, pk=entry_id)
    if request.method != 'POST':
        return redirect('ol_school_radio_detail', entry_id=entry.pk)
    saved = _upload_files(request, entry)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'saved': saved}, status=200 if saved else 400)
    if saved:
        messages.success(request, f'تم رفع {saved} ملفًا إلى مجلد يوم {entry.event_date:%Y-%m-%d}')
    elif not request.FILES:
        messages.error(request, 'اختر صورة أو ملفًا للرفع')
    return redirect('ol_school_radio_detail', entry_id=entry.pk)


@login_required
def school_radio_file_open(request, file_id):
    denied = _radio_permission_required(request, 'view')
    if denied:
        return denied
    radio_file = get_object_or_404(SchoolRadioFile, pk=file_id)
    if radio_file.google_drive_file_id:
        try:
            data, mimetype, name = GoogleDriveService().download_file(radio_file.google_drive_file_id)
        except Exception:
            messages.error(request, 'تعذّر فتح الملف من Google Drive؛ تحقق من الاتصال ثم حاول مجددًا')
            return redirect('ol_school_radio_detail', entry_id=radio_file.entry_id)
        response = HttpResponse(data, content_type=mimetype or 'application/octet-stream')
        response['Content-Disposition'] = f'inline; filename="{escape_uri_path(name)}"'
        return response
    if radio_file.google_drive_url:
        return redirect(radio_file.google_drive_url)
    return redirect('ol_school_radio_detail', entry_id=radio_file.entry_id)


@login_required
def school_radio_file_delete(request, file_id):
    denied = _radio_permission_required(request, 'edit')
    if denied:
        return denied
    radio_file = get_object_or_404(SchoolRadioFile, pk=file_id)
    entry_id = radio_file.entry_id
    if request.method == 'POST':
        if radio_file.google_drive_file_id:
            try:
                GoogleDriveService().delete_file(radio_file.google_drive_file_id)
            except Exception:
                messages.error(request, 'تعذّر حذف الملف من Google Drive؛ لم يُحذف من السجل')
                return redirect('ol_school_radio_detail', entry_id=entry_id)
        radio_file.delete()
        messages.success(request, 'تم حذف الملف')
    return redirect('ol_school_radio_detail', entry_id=entry_id)


def _generate_radio_content(request, entry, operation):
    topic = request.POST.get('topic', '').strip()[:300] or entry.topic.strip()
    if not topic:
        messages.error(request, 'اكتب موضوع الإذاعة أولًا، مثل يوم الأسير الفلسطيني أو القدس الشريف')
        return
    provider = get_provider()
    if not provider:
        messages.error(request, 'الذكاء الاصطناعي غير مهيأ؛ راجع AI_PROVIDER وAI_MODEL وAI_API_KEY في Vercel')
        return
    provider_name = getattr(provider, 'name', '')
    provider_model = getattr(provider, 'model', '')
    provider_name = provider_name if isinstance(provider_name, str) else ''
    provider_model = provider_model if isinstance(provider_model, str) else ''
    try:
        if operation == 'radio_word':
            data, tokens, duration = provider.generate_radio_word(topic)
            entry.ai_word = data
            success_message = 'تم إنشاء الكلمة كمسودة بانتظار مراجعتك'
        else:
            data, tokens, duration = provider.generate_radio_program(topic)
            entry.ai_program = data
            success_message = 'تم إنشاء برنامج إذاعي كامل كمسودة بانتظار مراجعتك'
        entry.topic = topic
        entry.ai_status = 'pending'
        entry.ai_generated_at = timezone.now()
        entry.ai_reviewed_by = None
        entry.save()
        log_usage(
            request.user, None, operation, provider=provider_name,
            model=provider_model, tokens=tokens, duration_ms=duration,
        )
        messages.success(request, success_message)
    except AIServiceUnavailable as exc:
        log_usage(
            request.user, None, operation, provider=provider_name,
            model=provider_model, success=False, error=str(exc),
        )
        messages.error(request, str(exc))
    except Exception:
        log_usage(
            request.user, None, operation, provider=provider_name,
            model=provider_model, success=False,
            error='تعذر إنشاء محتوى الإذاعة المدرسية',
        )
        messages.error(request, 'تعذّر إنشاء المحتوى الآن؛ لم يتغير المحتوى السابق')


@login_required
def school_radio_generate_word(request, entry_id):
    denied = _radio_permission_required(request, 'generate')
    if denied:
        return denied
    entry = get_object_or_404(SchoolRadioEntry, pk=entry_id)
    if request.method == 'POST':
        _generate_radio_content(request, entry, 'radio_word')
    return redirect('ol_school_radio_detail', entry_id=entry.pk)


@login_required
def school_radio_generate_program(request, entry_id):
    denied = _radio_permission_required(request, 'generate')
    if denied:
        return denied
    entry = get_object_or_404(SchoolRadioEntry, pk=entry_id)
    if request.method == 'POST':
        _generate_radio_content(request, entry, 'radio_program')
    return redirect('ol_school_radio_detail', entry_id=entry.pk)


@login_required
def school_radio_approve_ai(request, entry_id):
    denied = _radio_permission_required(request, 'review')
    if denied:
        return denied
    entry = get_object_or_404(SchoolRadioEntry, pk=entry_id)
    if request.method == 'POST':
        if not entry.ai_word and not entry.ai_program:
            messages.error(request, 'لا يوجد محتوى ذكي لاعتماده')
        else:
            entry.ai_status = 'approved'
            entry.ai_reviewed_by = request.user
            entry.save(update_fields=['ai_status', 'ai_reviewed_by', 'updated_at'])
            messages.success(request, 'تم اعتماد المحتوى بعد المراجعة')
    return redirect('ol_school_radio_detail', entry_id=entry.pk)


@login_required
def school_radio_delete(request, entry_id):
    denied = _radio_permission_required(request, 'delete')
    if denied:
        return denied
    entry = get_object_or_404(SchoolRadioEntry.objects.prefetch_related('files'), pk=entry_id)
    if request.method == 'POST':
        failed = 0
        for radio_file in entry.files.all():
            if radio_file.google_drive_file_id:
                try:
                    GoogleDriveService().delete_file(radio_file.google_drive_file_id)
                except Exception:
                    failed += 1
        entry.delete()
        if failed:
            messages.warning(request, f'حُذف السجل، وتعذّر حذف {failed} ملفًا من Google Drive')
        else:
            messages.success(request, 'تم حذف سجل الإذاعة وملفاته')
    return redirect('ol_school_radio_list')
