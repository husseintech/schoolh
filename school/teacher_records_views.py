from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Teacher, Class, Subject, SchoolInfo, TeacherScheduleEntry
from .teacher_records_models import CurriculumProgressRecord, TeacherTrainingRecord


def academic_year_today():
    y = date.today().year
    return f'{y}/{y+1}' if date.today().month >= 8 else f'{y-1}/{y}'


def _teacher(request):
    return getattr(request.user, 'teacher_profile', None)


def _allowed(request):
    return request.user.profile.role in ('admin', 'vice_principal', 'teacher')


def _teaching_pairs(teacher):
    pairs = TeacherScheduleEntry.objects.filter(teacher=teacher).values_list('subject_id','student_class_id').distinct()
    return set(pairs)


@login_required
def curriculum_records(request):
    if not _allowed(request):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    teacher = _teacher(request)
    is_admin = request.user.profile.role in ('admin','vice_principal')
    qs = CurriculumProgressRecord.objects.select_related('teacher','subject','student_class')
    if not is_admin:
        if not teacher: return redirect('dashboard')
        qs = qs.filter(teacher=teacher)
    if request.method == 'POST':
        selected_teacher = teacher
        if is_admin:
            selected_teacher = get_object_or_404(Teacher, id=request.POST.get('teacher_id'))
        subject = get_object_or_404(Subject, id=request.POST.get('subject_id'))
        student_class = get_object_or_404(Class, id=request.POST.get('class_id'))
        if not is_admin and (subject.id, student_class.id) not in _teaching_pairs(selected_teacher):
            messages.error(request, 'يمكنك التسجيل فقط للمواد والصفوف المرتبطة بجدولك')
            return redirect('curriculum_records')
        CurriculumProgressRecord.objects.create(
            teacher=selected_teacher, subject=subject, student_class=student_class,
            record_date=request.POST.get('record_date') or date.today(), academic_year=request.POST.get('academic_year') or academic_year_today(),
            assigned_pages=max(int(request.POST.get('assigned_pages') or 0),0), completed_pages=max(int(request.POST.get('completed_pages') or 0),0),
            notes=request.POST.get('notes','').strip(), principal_notes=request.POST.get('principal_notes','').strip() if is_admin else '', created_by=request.user)
        messages.success(request, 'تم حفظ سجل متابعة المنهاج')
        return redirect('curriculum_records')
    pairs = []
    if teacher and not is_admin:
        for e in TeacherScheduleEntry.objects.filter(teacher=teacher).select_related('subject','student_class').order_by('subject__name','student_class__name'):
            if not any(p['subject'].id==e.subject_id and p['student_class'].id==e.student_class_id for p in pairs): pairs.append({'subject':e.subject,'student_class':e.student_class})
    return render(request,'school/curriculum_records.html',{'records':qs,'teachers':Teacher.objects.all().order_by('full_name') if is_admin else [],'pairs':pairs,'subjects':Subject.objects.all().order_by('name'),'classes':Class.objects.all().order_by('name'),'is_admin':is_admin,'today':date.today(),'academic_year':academic_year_today()})


@login_required
def curriculum_record_delete(request, record_id):
    obj=get_object_or_404(CurriculumProgressRecord,id=record_id); teacher=_teacher(request); is_admin=request.user.profile.role in ('admin','vice_principal')
    if request.method!='POST' or (not is_admin and (not teacher or obj.teacher_id!=teacher.id)): messages.error(request,'ليس لديك صلاحية'); return redirect('curriculum_records')
    obj.delete(); messages.success(request,'تم حذف السجل'); return redirect('curriculum_records')


@login_required
def curriculum_records_print(request):
    if not _allowed(request): return redirect('dashboard')
    teacher=_teacher(request); is_admin=request.user.profile.role in ('admin','vice_principal'); qs=CurriculumProgressRecord.objects.select_related('teacher','subject','student_class')
    tid=request.GET.get('teacher')
    if not is_admin: qs=qs.filter(teacher=teacher)
    elif tid: qs=qs.filter(teacher_id=tid)
    return render(request,'school/curriculum_records_print.html',{'records':qs.order_by('teacher__full_name','record_date'),'info':SchoolInfo.objects.first(),'today':date.today()})


@login_required
def training_records(request):
    if not _allowed(request): messages.error(request,'ليس لديك صلاحية'); return redirect('dashboard')
    teacher=_teacher(request); is_admin=request.user.profile.role in ('admin','vice_principal'); qs=TeacherTrainingRecord.objects.select_related('teacher')
    if not is_admin:
        if not teacher: return redirect('dashboard')
        qs=qs.filter(teacher=teacher)
    if request.method=='POST':
        selected=teacher if not is_admin else get_object_or_404(Teacher,id=request.POST.get('teacher_id'))
        TeacherTrainingRecord.objects.create(teacher=selected,course_date=request.POST.get('course_date') or date.today(),course_name=request.POST.get('course_name','').strip(),course_location=request.POST.get('course_location','').strip(),target_group=request.POST.get('target_group','').strip(),outcomes=request.POST.get('outcomes','').strip(),notes=request.POST.get('notes','').strip(),created_by=request.user)
        messages.success(request,'تم حفظ سجل الدورة'); return redirect('training_records')
    return render(request,'school/training_records.html',{'records':qs,'teachers':Teacher.objects.all().order_by('full_name') if is_admin else [],'is_admin':is_admin,'today':date.today()})


@login_required
def training_record_delete(request, record_id):
    obj=get_object_or_404(TeacherTrainingRecord,id=record_id); teacher=_teacher(request); is_admin=request.user.profile.role in ('admin','vice_principal')
    if request.method!='POST' or (not is_admin and (not teacher or obj.teacher_id!=teacher.id)): messages.error(request,'ليس لديك صلاحية'); return redirect('training_records')
    obj.delete(); messages.success(request,'تم حذف السجل'); return redirect('training_records')


@login_required
def training_records_print(request):
    if not _allowed(request): return redirect('dashboard')
    teacher=_teacher(request); is_admin=request.user.profile.role in ('admin','vice_principal'); qs=TeacherTrainingRecord.objects.select_related('teacher'); tid=request.GET.get('teacher')
    if not is_admin: qs=qs.filter(teacher=teacher)
    elif tid: qs=qs.filter(teacher_id=tid)
    return render(request,'school/training_records_print.html',{'records':qs.order_by('teacher__full_name','course_date'),'info':SchoolInfo.objects.first(),'today':date.today()})
