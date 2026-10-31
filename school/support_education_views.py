from datetime import date
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from .models import Profile, Teacher, Class, Subject, UserPermission, SupportLessonAssignment, SupportLessonExecution

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
