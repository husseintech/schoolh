import mimetypes
from pathlib import Path
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import escape_uri_path
from open_learning.google_drive import GoogleDriveAuthError, GoogleDriveService
from .models import VisitProgramDriveFile, Teacher, has_perm

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png'}

def _files_redirect(teacher):
    return redirect(f'/visit-program/files/?teacher_id={teacher.pk}') if teacher else redirect('visit_program_files')

def _teacher_scope(user):
    """Return the linked teacher only for a signed-in teacher account."""
    if getattr(getattr(user, 'profile', None), 'role', None) != 'teacher':
        return None
    return getattr(user, 'teacher_profile', None)


def _allowed(request, action):
    # Teachers may view assigned files only; upload/delete require staff permissions.
    teacher = _teacher_scope(request.user)
    if teacher and action == 'view':
        return True
    if has_perm(request.user, 'inspection_visits', action):
        return True
    messages.error(request, 'ليس لديك صلاحية للوصول إلى أرشيف ملفات الزيارات.')
    return False

@login_required
def visit_program_files(request):
    if not _allowed(request, 'view'):
        return redirect('visit_program_list')
    teacher_scope = _teacher_scope(request.user)
    teacher_id = request.GET.get('teacher_id') or request.POST.get('teacher_id') or ''
    # Ignore teacher_id supplied by a teacher account; it must always be their own linked profile.
    if teacher_scope:
        teacher = teacher_scope
    else:
        teacher = get_object_or_404(Teacher, pk=teacher_id) if str(teacher_id).isdigit() else None
    if request.method == 'POST':
        if not _allowed(request, 'add'):
            return redirect('visit_program_list')
        uploaded = request.FILES.get('file')
        if not uploaded:
            messages.error(request, 'اختر ملفًا قبل الرفع.')
            return _files_redirect(teacher)
        extension = Path(uploaded.name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            messages.error(request, 'نوع الملف غير مدعوم. المسموح PDF وWord وExcel وPowerPoint والصور JPG/PNG.')
            return _files_redirect(teacher)
        if uploaded.size > MAX_FILE_SIZE:
            messages.error(request, 'حجم الملف يتجاوز 10 ميغابايت.')
            return _files_redirect(teacher)
        service = GoogleDriveService()
        if not service.is_connected():
            messages.error(request, 'Google Drive غير متصل. اربطه من إعدادات التخزين في قسم التعلم المفتوح أولًا.')
            return _files_redirect(teacher)
        try:
            data = uploaded.read()
            mime_type = uploaded.content_type or mimetypes.guess_type(uploaded.name)[0] or 'application/octet-stream'
            result = service.upload_to_folder_path(Path(uploaded.name).name, data, mime_type, ['أرشيف تقارير الزيارات الميدانية'])
            VisitProgramDriveFile.objects.create(
                teacher=teacher,
                file_name=result.get('name') or Path(uploaded.name).name,
                mime_type=result.get('mimeType') or mime_type,
                file_size=int(result.get('size') or uploaded.size or 0) or None,
                google_drive_file_id=result['id'],
                google_drive_url=result.get('webViewLink', ''),
                uploaded_by=request.user,
            )
            messages.success(request, 'تم رفع الملف وحفظه في Google Drive بنجاح.')
        except GoogleDriveAuthError:
            messages.error(request, 'انتهى اتصال Google Drive. أعد ربط الحساب من إعدادات التخزين ثم حاول مجددًا.')
        except Exception:
            messages.error(request, 'تعذّر رفع الملف إلى Google Drive. لم يُسجل الملف في الأرشيف؛ حاول مرة أخرى.')
        return redirect(f"/visit-program/files/?teacher_id={teacher.pk}") if teacher else redirect('visit_program_files')
    files = VisitProgramDriveFile.objects.select_related('uploaded_by', 'teacher').all()
    if teacher_scope:
        files = files.filter(teacher=teacher_scope)
    elif teacher:
        files = files.filter(teacher=teacher)
    return render(request, 'school/visit_program_files.html', {
        'files': files,
        'teacher': teacher,
        'gdrive_connected': GoogleDriveService().is_connected(),
        'can_upload': has_perm(request.user, 'inspection_visits', 'add'),
        'can_delete': has_perm(request.user, 'inspection_visits', 'delete'),
    })

@login_required
def visit_program_file_open(request, file_id):
    if not _allowed(request, 'view'):
        return redirect('visit_program_list')
    record = get_object_or_404(VisitProgramDriveFile, pk=file_id)
    teacher_scope = _teacher_scope(request.user)
    if teacher_scope and record.teacher_id != teacher_scope.pk:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('لا يمكنك الوصول إلى ملف غير مخصص لك.')
    try:
        content, mime_type, drive_name = GoogleDriveService().download_file(record.google_drive_file_id)
    except Exception:
        messages.error(request, 'تعذّر فتح الملف من Google Drive. تحقق من اتصال Drive ثم أعد المحاولة.')
        return redirect('visit_program_files')
    disposition = 'attachment' if request.GET.get('download') == '1' else 'inline'
    response = HttpResponse(content, content_type=mime_type or record.mime_type or 'application/octet-stream')
    response['Content-Disposition'] = f"{disposition}; filename*=UTF-8''{escape_uri_path(record.file_name or drive_name)}"
    response['X-Content-Type-Options'] = 'nosniff'
    return response

@login_required
def visit_program_file_delete(request, file_id):
    if request.method != 'POST' or not _allowed(request, 'delete'):
        return redirect('visit_program_files')
    record = get_object_or_404(VisitProgramDriveFile, pk=file_id)
    try:
        GoogleDriveService().delete_file(record.google_drive_file_id)
        record.delete()
        messages.success(request, 'تم حذف الملف من Google Drive والأرشيف.')
    except Exception:
        messages.error(request, 'تعذّر حذف الملف من Google Drive؛ لم يُحذف سجل الأرشيف.')
    return redirect('visit_program_files')
