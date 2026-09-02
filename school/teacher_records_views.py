from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Teacher, Class, Subject, SchoolInfo, TeacherScheduleEntry
from .teacher_records_models import CurriculumProgressRecord, TeacherTrainingRecord, ClassSubjectMapping


def academic_year_today():
    y = date.today().year
    return f'{y}/{y+1}' if date.today().month >= 8 else f'{y-1}/{y}'


def _teacher(request):
    return getattr(request.user, 'teacher_profile', None)


def _allowed(request):
    return request.user.profile.role in ('admin', 'vice_principal', 'teacher')


def _teacher_options(teacher):
    schedule_pairs = list(
        TeacherScheduleEntry.objects.filter(
            teacher=teacher, subject__isnull=False, student_class__isnull=False
        ).select_related('subject', 'student_class').order_by('subject__name', 'student_class__name')
    )
    pairs = []
    seen = set()
    if schedule_pairs:
        for e in schedule_pairs:
            key = (e.subject_id, e.student_class_id)
            if key not in seen:
                seen.add(key)
                pairs.append((e.subject, e.student_class))
    else:
        teacher_subject_ids = set(teacher.subjects.values_list('id', flat=True))
        teacher_class_ids = set(teacher.classes.values_list('id', flat=True))
        mappings = ClassSubjectMapping.objects.filter(
            subject_id__in=teacher_subject_ids,
            student_class_id__in=teacher_class_ids,
        ).select_related('subject', 'student_class').order_by('subject__name', 'student_class__name')
        for m in mappings:
            pairs.append((m.subject, m.student_class))

    grouped = {}
    for subject, student_class in pairs:
        item = grouped.setdefault(subject.id, {'id': subject.id, 'name': subject.name, 'classes': []})
        item['classes'].append({
            'id': student_class.id,
            'name': student_class.name,
            'students': student_class.students.count(),
        })
    return list(grouped.values())


def _allowed_pair_ids(teacher):
    return {
        (subject['id'], cls['id'])
        for subject in _teacher_options(teacher)
        for cls in subject['classes']
    }


@login_required
def curriculum_records(request):
    if not _allowed(request):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    teacher = _teacher(request)
    is_admin = request.user.profile.role in ('admin', 'vice_principal')
    qs = CurriculumProgressRecord.objects.select_related('teacher', 'subject', 'student_class').prefetch_related('student_classes')
    if not is_admin:
        if not teacher:
            return redirect('dashboard')
        qs = qs.filter(teacher=teacher)

    teachers = list(Teacher.objects.all().order_by('full_name')) if is_admin else []
    teacher_map = {str(t.id): _teacher_options(t) for t in teachers}
    own_options = _teacher_options(teacher) if teacher and not is_admin else []

    if request.method == 'POST':
        selected_teacher = teacher
        if is_admin:
            selected_teacher = get_object_or_404(Teacher, id=request.POST.get('teacher_id'))
        subject = get_object_or_404(Subject, id=request.POST.get('subject_id'))
        class_ids = [int(x) for x in request.POST.getlist('class_ids') if str(x).isdigit()]
        if not class_ids:
            messages.error(request, 'اختر صفاً واحداً على الأقل')
            return redirect('curriculum_records')
        classes = list(Class.objects.filter(id__in=class_ids).order_by('name'))
        allowed_pairs = _allowed_pair_ids(selected_teacher)
        invalid = [c for c in classes if (subject.id, c.id) not in allowed_pairs]
        if invalid or len(classes) != len(set(class_ids)):
            messages.error(request, 'يمكن التسجيل فقط للمبحث والصفوف التي يدرّسها المعلم')
            return redirect('curriculum_records')
        obj = CurriculumProgressRecord.objects.create(
            teacher=selected_teacher,
            subject=subject,
            student_class=classes[0],
            record_date=request.POST.get('record_date') or date.today(),
            academic_year=request.POST.get('academic_year') or academic_year_today(),
            assigned_pages=max(int(request.POST.get('assigned_pages') or 0), 0),
            completed_pages=max(int(request.POST.get('completed_pages') or 0), 0),
            notes=request.POST.get('notes', '').strip(),
            principal_notes=request.POST.get('principal_notes', '').strip() if is_admin else '',
            created_by=request.user,
        )
        obj.student_classes.set(classes)
        total_students = sum(c.students.count() for c in classes)
        messages.success(request, f'تم حفظ سجل متابعة المنهاج لـ {len(classes)} صف/شعبة، بإجمالي {total_students} طالباً')
        return redirect('curriculum_records')

    return render(request, 'school/curriculum_records.html', {
        'records': qs,
        'teachers': teachers,
        'is_admin': is_admin,
        'today': date.today(),
        'academic_year': academic_year_today(),
        'teacher_map': teacher_map,
        'own_options': own_options,
    })


@login_required
def curriculum_record_delete(request, record_id):
    obj = get_object_or_404(CurriculumProgressRecord, id=record_id)
    teacher = _teacher(request)
    is_admin = request.user.profile.role in ('admin', 'vice_principal')
    if request.method != 'POST' or (not is_admin and (not teacher or obj.teacher_id != teacher.id)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('curriculum_records')
    obj.delete()
    messages.success(request, 'تم حذف السجل')
    return redirect('curriculum_records')


@login_required
def curriculum_records_print(request):
    if not _allowed(request):
        return redirect('dashboard')
    teacher = _teacher(request)
    is_admin = request.user.profile.role in ('admin', 'vice_principal')
    qs = CurriculumProgressRecord.objects.select_related('teacher', 'subject', 'student_class').prefetch_related('student_classes')
    tid = request.GET.get('teacher')
    if not is_admin:
        qs = qs.filter(teacher=teacher)
    elif tid:
        qs = qs.filter(teacher_id=tid)
    return render(request, 'school/curriculum_records_print.html', {'records': qs.order_by('teacher__full_name', 'record_date'), 'info': SchoolInfo.objects.first(), 'today': date.today()})


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
