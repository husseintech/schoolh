from django.contrib import messages
from django.shortcuts import redirect

from .teacher_records_models import ClassSubjectMapping, CurriculumProgressRecord, TeacherTrainingRecord

TEACHER_RECORD_CLEARABLE_TABLES = [
    ('class_subjects', 'مواد الصفوف', ClassSubjectMapping),
    ('curriculum', 'سجل متابعة ما قطع من المنهاج', CurriculumProgressRecord),
    ('training', 'سجل الدورات', TeacherTrainingRecord),
]


def handle_teacher_record_reset(request):
    if request.method != 'POST' or request.path.rstrip('/') != '/reset-data':
        return None
    if request.POST.get('action') != 'flush_one' or request.POST.get('confirm') != 'YES':
        return None
    key = request.POST.get('key', '')
    for table_key, label, model in TEACHER_RECORD_CLEARABLE_TABLES:
        if key == table_key:
            if request.user.profile.role != 'admin':
                messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
                return redirect('dashboard')
            count = model.objects.count()
            model.objects.all().delete()
            messages.success(request, f'تم تفريغ: {label} ({count} سجل)')
            return redirect('reset_data')
    return None


def reset_rows_html(request):
    token = request.META.get('CSRF_COOKIE', '')
    rows = []
    for key, label, model in TEACHER_RECORD_CLEARABLE_TABLES:
        count = model.objects.count()
        rows.append(f'''<tr data-teacher-record-reset="1"><td>{label}</td><td><span class="badge bg-secondary">{count}</span></td><td class="text-center"><form method="post" style="display:inline" onsubmit="return confirm('سيتم حذف {count} سجل من «{label}» نهائياً. هل أنت متأكد؟')"><input type="hidden" name="csrfmiddlewaretoken" value="{token}"><input type="hidden" name="action" value="flush_one"><input type="hidden" name="key" value="{key}"><input type="hidden" name="confirm" value="YES"><button type="submit" class="btn btn-outline-danger btn-sm"><i class="bi bi-trash"></i> تفريغ</button></form></td></tr>''')
    return ''.join(rows)
