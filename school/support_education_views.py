from datetime import date
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from .models import Profile, Teacher, Class, Subject, UserPermission, SupportLessonAssignment, SupportLessonExecution, SupportTeacherAttendance

logger = logging.getLogger(__name__)


def _role(user):
    return getattr(getattr(user, 'profile', None), 'role', '')


def _support_teacher(user):
    return _role(user) == 'support_teacher' and hasattr(user, 'teacher_profile')


@login_required
def support_teacher_manage(request):
    if _role(request.user) != 'admin':
        messages.error(request, 'هذه الصفحة للإدارة فقط')
        return redirect('dashboard')
    if request.method == 'POST':
        name = request.POST.get('full_name', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        specialization = request.POST.get('specialization', '').strip()
        if not all([name, username, password]):
            messages.error(request, 'يرجى إدخال الاسم واسم المستخدم وكلمة المرور')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'اسم المستخدم مستخدم مسبقاً')
        else:
            user = User.objects.create_user(username=username, password=password, first_name=name)
            Profile.objects.create(user=user, role='support_teacher')
            UserPermission.objects.get_or_create(user=user, defaults={'permissions': {}})
            Teacher.objects.create(user=user, full_name=name, specialization=specialization)
            messages.success(request, 'تم إنشاء حساب المعلم المساند بنجاح')
            return redirect('support_teacher_manage')
    teachers = Teacher.objects.filter(user__profile__role='support_teacher').select_related('user').order_by('full_name')
    return render(request, 'school/support_teacher_manage.html', {'support_teachers': teachers})


@login_required
def support_teacher_edit(request, teacher_id):
    if _role(request.user) != 'admin':
        messages.error(request, 'هذه الصفحة للإدارة فقط')
        return redirect('dashboard')
    teacher = get_object_or_404(
        Teacher.objects.select_related('user'),
        pk=teacher_id,
        user__profile__role='support_teacher',
    )
    user = teacher.user
    if request.method == 'POST':
        name = request.POST.get('full_name', '').strip()
        username = request.POST.get('username', '').strip()
        specialization = request.POST.get('specialization', '').strip()
        password = request.POST.get('password', '').strip()
        if not name or not username:
            messages.error(request, 'يرجى إدخال الاسم واسم المستخدم')
        elif User.objects.filter(username=username).exclude(pk=user.pk).exists():
            messages.error(request, 'اسم المستخدم مستخدم مسبقاً')
        else:
            teacher.full_name = name
            teacher.specialization = specialization
            teacher.save(update_fields=['full_name', 'specialization'])
            user.username = username
            user.first_name = name
            if password:
                user.set_password(password)
            user.save()
            messages.success(request, 'تم تحديث بيانات المعلم المساند بنجاح')
            return redirect('support_teacher_manage')
    return render(request, 'school/support_teacher_manage.html', {
        'support_teachers': Teacher.objects.filter(
            user__profile__role='support_teacher'
        ).select_related('user').order_by('full_name'),
        'editing_teacher': teacher,
    })


@login_required
def support_teacher_delete(request, teacher_id):
    if _role(request.user) != 'admin':
        messages.error(request, 'هذه الصفحة للإدارة فقط')
        return redirect('dashboard')
    if request.method != 'POST':
        return redirect('support_teacher_manage')
    teacher = get_object_or_404(
        Teacher.objects.select_related('user'),
        pk=teacher_id,
        user__profile__role='support_teacher',
    )
    if SupportLessonExecution.objects.filter(support_teacher=teacher).exists():
        messages.error(
            request,
            'لا يمكن حذف هذا المعلم لأنه يملك متابعات مسجلة. حفاظاً على سجلات التعليم المساند، يمكنك تعديل بيانات حسابه بدلاً من حذفه.'
        )
        return redirect('support_teacher_manage')
    teacher.user.delete()
    messages.success(request, 'تم حذف حساب المعلم المساند')
    return redirect('support_teacher_manage')


@login_required
def support_assignment_list(request):
    if _role(request.user) != 'teacher':
        messages.error(request, 'تسجيل المتابعات متاح للمعلم الأصيل فقط')
        return redirect('support_dashboard')
    teacher = get_object_or_404(Teacher, user=request.user)
    classes = teacher.classes.all().order_by('name')
    subjects = teacher.subjects.all().order_by('name')
    if not subjects.exists():
        subjects = Subject.objects.all().order_by('name')
    assignments = SupportLessonAssignment.objects.filter(
        original_teacher=teacher
    ).select_related('class_obj', 'subject').prefetch_related(
        'executions__support_teacher'
    ).order_by('-assignment_date', '-created_at')
    if request.method == 'POST':
        class_obj = get_object_or_404(classes, pk=request.POST.get('class_id'))
        subject = get_object_or_404(subjects, pk=request.POST.get('subject_id'))
        title = request.POST.get('lesson_title', '').strip()
        required = request.POST.get('required_work', '').strip()
        if not title or not required:
            messages.error(request, 'يرجى إدخال اسم الدرس والمطلوب من التعليم المساند')
        else:
            SupportLessonAssignment.objects.create(
                class_obj=class_obj,
                subject=subject,
                original_teacher=teacher,
                assignment_date=timezone.localdate(),
                lesson_title=title,
                required_work=required,
            )
            messages.success(request, 'تم حفظ المتابعة بنجاح')
            return redirect('support_assignment_list')
    return render(request, 'school/support_assignment_list.html', {
        'classes': classes, 'subjects': subjects, 'assignments': assignments,
        'today': timezone.localdate(),
    })




@login_required
def support_teacher_attendance(request):
    if not _support_teacher(request.user):
        messages.error(request, 'هذه الصفحة مخصصة للمعلم المساند فقط')
        return redirect('dashboard')
    teacher = get_object_or_404(Teacher, user=request.user)
    selected_date = timezone.localdate()
    if request.method == 'POST':
        parsed = parse_date(request.POST.get('attendance_date', ''))
        if not parsed:
            messages.error(request, 'يرجى اختيار تاريخ صحيح')
            return redirect('support_teacher_attendance')
        selected_date = parsed
        record, created = SupportTeacherAttendance.objects.get_or_create(
            teacher=teacher,
            attendance_date=selected_date,
            defaults={'check_in_time': '07:30', 'check_out_time': '14:30'},
        )
        if created:
            messages.success(request, 'تم تسجيل بداية ونهاية الدوام بنجاح')
        else:
            messages.warning(request, 'تم تسجيل بصمة هذا اليوم مسبقاً ولا يمكن تكرارها')
        return redirect('support_teacher_attendance')
    records = list(SupportTeacherAttendance.objects.filter(
        teacher=teacher
    ).order_by('-attendance_date'))
    arabic_days = {
        0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء',
        3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد',
    }
    for record in records:
        record.day_name = arabic_days[record.attendance_date.weekday()]
    return render(request, 'school/support_teacher_attendance.html', {
        'teacher': teacher,
        'records': records,
        'selected_date': selected_date,
    })


@login_required
def support_dashboard(request):
    if _support_teacher(request.user):
        teacher = request.user.teacher_profile
        # المساند يستطيع استعراض جميع صفوف المدرسة، وليس صفوفاً محددة مسبقاً.
        classes = Class.objects.all().order_by('name')
        subjects = Subject.objects.all().order_by('name')
        selected_id = request.GET.get('class_id', '')
        subject_id = request.GET.get('subject_id', '')
        selected = get_object_or_404(classes, pk=selected_id) if selected_id else None
        selected_subject = get_object_or_404(subjects, pk=subject_id) if subject_id else None
        assignment = None
        if selected and selected_subject:
            assignment = SupportLessonAssignment.objects.filter(
                class_obj=selected, subject=selected_subject
            ).select_related('original_teacher', 'subject', 'class_obj').order_by(
                '-assignment_date', '-created_at', '-id'
            ).first()
        executions = SupportLessonExecution.objects.filter(
            support_teacher=teacher
        ).select_related('assignment__class_obj', 'assignment__subject', 'assignment__original_teacher')
        if request.method == 'POST':
            target = get_object_or_404(
                SupportLessonAssignment.objects.select_related('class_obj', 'subject'),
                pk=request.POST.get('assignment_id')
            )
            notes = request.POST.get('notes', '').strip()
            if not notes:
                messages.error(request, 'يرجى كتابة ما تم تنفيذه أو ملاحظات المتابعة')
            else:
                SupportLessonExecution.objects.create(
                    assignment=target,
                    support_teacher=teacher,
                    execution_date=timezone.localdate(),
                    notes=notes,
                )
                messages.success(request, 'تم حفظ متابعة المعلم المساند')
                return redirect('/support-education/?class_id=%s&subject_id=%s' % (
                    target.class_obj_id, target.subject_id or ''
                ))
        return render(request, 'school/support_teacher_dashboard.html', {
            'classes': classes, 'subjects': subjects, 'selected_class': selected,
            'selected_subject': selected_subject, 'assignment': assignment,
            'executions': executions, 'today': timezone.localdate(),
        })
    if _role(request.user) not in ('admin', 'vice_principal', 'secretary'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    return redirect('support_reports')


@login_required
def support_reports(request):
    if _role(request.user) not in ('admin', 'vice_principal', 'secretary'):
        messages.error(request, 'ليس لديك صلاحية لعرض التقارير')
        return redirect('dashboard')
    qs = SupportLessonAssignment.objects.select_related(
        'class_obj', 'subject', 'original_teacher'
    ).prefetch_related('executions__support_teacher')
    class_id = request.GET.get('class_id', '')
    subject_id = request.GET.get('subject_id', '')
    original_id = request.GET.get('original_teacher', '')
    support_id = request.GET.get('support_teacher', '')
    start = parse_date(request.GET.get('from_date', ''))
    end = parse_date(request.GET.get('to_date', ''))
    if class_id:
        qs = qs.filter(class_obj_id=class_id)
    if subject_id:
        qs = qs.filter(subject_id=subject_id)
    if original_id:
        qs = qs.filter(original_teacher_id=original_id)
    if support_id:
        qs = qs.filter(executions__support_teacher_id=support_id).distinct()
    if start:
        qs = qs.filter(assignment_date__gte=start)
    if end:
        qs = qs.filter(assignment_date__lte=end)
    return render(request, 'school/support_education_report.html', {
        'assignments': qs.order_by('-assignment_date', '-created_at'),
        'classes': Class.objects.all().order_by('name'),
        'subjects': Subject.objects.all().order_by('name'),
        'original_teachers': Teacher.objects.filter(user__profile__role='teacher').order_by('full_name'),
        'support_teachers': Teacher.objects.filter(user__profile__role='support_teacher').order_by('full_name'),
        'filters': request.GET,
    })

@login_required
def admin_support_teacher_attendance(request):
    """Admin management, editing and printing of support-teacher attendance."""
    if _role(request.user) != 'admin':
        messages.error(request, 'هذه الصفحة للإدارة فقط')
        return redirect('dashboard')

    teachers = Teacher.objects.filter(
        user__profile__role='support_teacher'
    ).select_related('user').order_by('full_name')

    today = timezone.localdate()
    teacher_id = request.GET.get('teacher_id') or request.POST.get('teacher_id') or ''
    try:
        year = int(request.GET.get('year') or request.POST.get('year') or today.year)
        month = int(request.GET.get('month') or request.POST.get('month') or today.month)
        if month < 1 or month > 12 or year < 2000 or year > 2100:
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month

    selected_teacher = teachers.filter(pk=teacher_id).first() if teacher_id else None

    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        target_id = request.POST.get('record_id')
        if action == 'delete':
            record = get_object_or_404(
                SupportTeacherAttendance,
                pk=target_id,
                teacher__user__profile__role='support_teacher',
            )
            record.delete()
            messages.success(request, 'تم حذف سجل البصمة بنجاح')
        else:
            parsed_date = parse_date(request.POST.get('attendance_date', ''))
            check_in = parse_time(request.POST.get('check_in_time', '07:30'))
            check_out = parse_time(request.POST.get('check_out_time', '14:30'))
            if not selected_teacher:
                messages.error(request, 'يرجى اختيار المعلم المساند')
            elif not parsed_date or not check_in or not check_out:
                messages.error(request, 'يرجى إدخال تاريخ وأوقات صحيحة')
            else:
                if action == 'update':
                    record = get_object_or_404(
                        SupportTeacherAttendance,
                        pk=target_id,
                        teacher__user__profile__role='support_teacher',
                    )
                    duplicate = SupportTeacherAttendance.objects.filter(
                        teacher=selected_teacher, attendance_date=parsed_date
                    ).exclude(pk=record.pk).exists()
                    if duplicate:
                        messages.error(request, 'توجد بصمة مسجلة لهذا المعلم في التاريخ نفسه')
                    else:
                        record.teacher = selected_teacher
                        record.attendance_date = parsed_date
                        record.check_in_time = check_in
                        record.check_out_time = check_out
                        record.save()
                        messages.success(request, 'تم تعديل سجل البصمة بنجاح')
                else:
                    record, created = SupportTeacherAttendance.objects.get_or_create(
                        teacher=selected_teacher,
                        attendance_date=parsed_date,
                        defaults={'check_in_time': check_in, 'check_out_time': check_out},
                    )
                    if created:
                        messages.success(request, 'تمت إضافة البصمة بنجاح')
                    else:
                        messages.warning(request, 'توجد بصمة مسجلة لهذا المعلم في التاريخ نفسه')
        return redirect(
            f"{request.path}?teacher_id={teacher_id}&year={year}&month={month}"
        )

    records = SupportTeacherAttendance.objects.none()
    if selected_teacher:
        records = SupportTeacherAttendance.objects.filter(
            teacher=selected_teacher,
            attendance_date__year=year,
            attendance_date__month=month,
        ).order_by('attendance_date', 'id')

    arabic_days = {
        0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء',
        3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد',
    }
    for record in records:
        record.day_name = arabic_days[record.attendance_date.weekday()]

    return render(request, 'school/admin_support_teacher_attendance.html', {
        'support_teachers': teachers,
        'selected_teacher': selected_teacher,
        'records': records,
        'year': year,
        'month': month,
        'month_name': [
            '', 'كانون الثاني', 'شباط', 'آذار', 'نيسان', 'أيار', 'حزيران',
            'تموز', 'آب', 'أيلول', 'تشرين الأول', 'تشرين الثاني', 'كانون الأول'
        ][month],
        'today': today,
    })
