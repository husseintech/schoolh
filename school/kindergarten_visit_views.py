import os
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .models import Teacher, SchoolInfo, KindergartenVisitReport, KindergartenVisitAttachment, has_perm


def _is_kindergarten_teacher(teacher):
    return teacher.classes.filter(name__iexact='تمهيدي').exists()


def _can_manage(request):
    return has_perm(request.user, 'inspection_visits', 'view') and has_perm(request.user, 'inspection_visits', 'add')


@login_required
def kindergarten_visit_form(request, teacher_id, report_id=None):
    if not _can_manage(request):
        messages.error(request, 'ليس لديك صلاحية لتسجيل تقارير الزيارات.')
        return redirect('visit_program_list')
    teacher = get_object_or_404(Teacher.objects.prefetch_related('classes'), pk=teacher_id)
    if not _is_kindergarten_teacher(teacher):
        messages.error(request, 'هذا النموذج مخصص لمربية الصف التمهيدي فقط.')
        return redirect('visit_program_list')
    report = get_object_or_404(KindergartenVisitReport, pk=report_id, teacher=teacher) if report_id else None
    fields = [
        'scientific_qualification', 'professional_qualification', 'experience_years', 'daily_preparation', 'activity',
        'activity_start', 'activity_end', 'preparation', 'objectives',
        'teaching_aids', 'aids_adequacy', 'method', 'teaching_style',
        'children_interaction', 'individual_differences', 'group_work', 'whole_group_count', 'small_group_count',
        'goals_achieved', 'strengths', 'improvement_notes',
        'principal_signature', 'teacher_signature',
    ]
    if request.method == 'POST':
        if report is None:
            report = KindergartenVisitReport(teacher=teacher, created_by=request.user)
        report.visit_date = request.POST.get('visit_date') or timezone.localdate()
        school_info = SchoolInfo.objects.first()
        if school_info:
            report.school_name = school_info.name_ar
        for field in fields:
            setattr(report, field, request.POST.get(field, '').strip())
        report.save()
        for uploaded in request.FILES.getlist('attachments'):
            if uploaded.size > 10 * 1024 * 1024:
                messages.warning(request, f'تم حفظ التقرير، لكن الملف {uploaded.name} تجاوز 10 ميغابايت ولم يُرفق.')
                continue
            KindergartenVisitAttachment.objects.create(
                report=report, file=uploaded, original_name=os.path.basename(uploaded.name),
                uploaded_by=request.user,
            )
        messages.success(request, 'تم حفظ تقرير زيارة التمهيدي.')
        return redirect('kindergarten_visit_edit', teacher_id=teacher.pk, report_id=report.pk)
    reports = KindergartenVisitReport.objects.filter(teacher=teacher).prefetch_related('attachments')
    school_info = SchoolInfo.objects.first()
    return render(request, 'school/kindergarten_visit_form.html', {
        'teacher': teacher, 'report': report, 'reports': reports,
        'today': timezone.localdate(), 'school_info': school_info,
    })


@login_required
def kindergarten_visit_edit(request, teacher_id, report_id):
    return kindergarten_visit_form(request, teacher_id, report_id)
