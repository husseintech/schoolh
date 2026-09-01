from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Notification, SchoolInfo, SupervisorVisit, Teacher, has_perm
from .services import send_push
from .supervisor_followup_models import SupervisorVisitFollowup


def _can_view(user):
    return has_perm(user, 'supervisor_visits', 'view') or user.profile.role in ('admin', 'vice_principal')


def _can_followup(user):
    return has_perm(user, 'supervisor_visits', 'edit') or user.profile.role in ('admin', 'vice_principal')


def _is_followed(visit):
    return hasattr(visit, 'management_followup') or bool((visit.admin_followup or '').strip())


@login_required
def supervisor_visit_list(request):
    if not _can_view(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')

    teachers = Teacher.objects.all().order_by('full_name')
    selected_teacher = None
    teacher_id = request.GET.get('teacher_id', '').strip()
    status = request.GET.get('status', '').strip()

    visits = SupervisorVisit.objects.select_related('teacher').select_related('management_followup')
    if teacher_id:
        selected_teacher = get_object_or_404(Teacher, id=teacher_id)
        visits = visits.filter(teacher=selected_teacher)
    elif not status:
        visits = SupervisorVisit.objects.none()

    if status == 'pending':
        visits = visits.filter(management_followup__isnull=True, admin_followup='')
    elif status == 'followed':
        from django.db.models import Q
        visits = visits.filter(Q(management_followup__isnull=False) | ~Q(admin_followup='')).distinct()

    if request.method == 'POST':
        if not has_perm(request.user, 'supervisor_visits', 'add'):
            messages.error(request, 'ليس لديك صلاحية للإضافة')
            return redirect('supervisor_visit_list')
        teacher_id = request.POST.get('teacher_id')
        selected_teacher = get_object_or_404(Teacher, id=teacher_id) if teacher_id else None
        if not selected_teacher:
            messages.error(request, 'الرجاء اختيار معلم')
            return redirect('supervisor_visit_list')

        visit = SupervisorVisit.objects.create(
            teacher=selected_teacher,
            visit_number=request.POST.get('visit_number', ''),
            visit_date=request.POST.get('visit_date', ''),
            subject_area=request.POST.get('subject_area', ''),
            lesson_topic=request.POST.get('lesson_topic', ''),
            class_name=request.POST.get('class_name', ''),
            section=request.POST.get('section', ''),
            supervisor_name=request.POST.get('supervisor_name', ''),
            recommendations=request.POST.get('recommendations', ''),
            admin_followup='',
            created_by=request.user,
        )
        if selected_teacher.user:
            recs = request.POST.get('recommendations', '').strip()
            msg = f'تم تسجيل زيارة مشرف بتاريخ {visit.visit_date}'
            if recs:
                msg += f'\nتوصيات المشرف: {recs[:500]}'
            Notification.objects.create(
                user=selected_teacher.user,
                title='زيارة مشرف جديدة',
                message=msg,
                link=f'/supervisor-visits/{visit.id}/report/',
            )
            send_push(
                selected_teacher.user,
                'زيارة مشرف جديدة',
                f'تم تسجيل زيارة مشرف بتاريخ {visit.visit_date}',
                f'/supervisor-visits/{visit.id}/report/',
            )
        messages.success(request, 'تم حفظ الزيارة. أصبحت الآن بانتظار متابعة الإدارة.')
        return redirect(f'/supervisor-visits/?teacher_id={selected_teacher.id}')

    visits = list(visits.order_by('-visit_date', '-created_at'))
    for visit in visits:
        visit.followed = _is_followed(visit)

    pending_count = SupervisorVisit.objects.filter(management_followup__isnull=True, admin_followup='').count()
    followed_count = SupervisorVisit.objects.exclude(management_followup__isnull=True, admin_followup='').count()
    return render(request, 'school/supervisor_visit_list.html', {
        'teachers': teachers,
        'selected_teacher': selected_teacher,
        'visits': visits,
        'status': status,
        'pending_count': pending_count,
        'followed_count': followed_count,
        'can_followup': _can_followup(request.user),
    })


@login_required
def supervisor_visit_report(request, visit_id):
    if not _can_view(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    visit = get_object_or_404(
        SupervisorVisit.objects.select_related('teacher').select_related('management_followup'),
        id=visit_id,
    )
    followup = getattr(visit, 'management_followup', None)
    return render(request, 'school/supervisor_visit_report.html', {
        'visit': visit,
        'followup': followup,
        'legacy_followup': (visit.admin_followup or '').strip(),
        'followed': _is_followed(visit),
        'can_followup': _can_followup(request.user),
        'info': SchoolInfo.objects.first(),
    })


@login_required
def supervisor_visit_followup(request, visit_id):
    if not _can_followup(request.user):
        messages.error(request, 'ليس لديك صلاحية لإضافة متابعة الإدارة')
        return redirect('dashboard')

    visit = get_object_or_404(SupervisorVisit.objects.select_related('teacher'), id=visit_id)
    followup = SupervisorVisitFollowup.objects.filter(visit=visit).first()

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        followup_date = request.POST.get('followup_date', '').strip()
        if not notes or not followup_date:
            messages.error(request, 'تاريخ المتابعة ونص المتابعة مطلوبان')
        else:
            SupervisorVisitFollowup.objects.update_or_create(
                visit=visit,
                defaults={
                    'followup_date': followup_date,
                    'notes': notes,
                    'created_by': request.user,
                },
            )
            messages.success(request, 'تم حفظ متابعة الإدارة وتاريخها بنجاح')
            return redirect('supervisor_visit_report', visit_id=visit.id)

    return render(request, 'school/supervisor_visit_followup.html', {
        'visit': visit,
        'followup': followup,
        'today': timezone.localdate(),
    })


@login_required
def supervisor_visits_report(request):
    if not _can_view(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')

    visits = SupervisorVisit.objects.select_related('teacher').select_related('management_followup').order_by('-visit_date')
    teachers = Teacher.objects.all().order_by('full_name')
    selected_teacher_id = request.GET.get('teacher_id', '').strip()
    status = request.GET.get('status', '').strip()
    if selected_teacher_id:
        visits = visits.filter(teacher_id=selected_teacher_id)
    if status == 'pending':
        visits = visits.filter(management_followup__isnull=True, admin_followup='')
    elif status == 'followed':
        from django.db.models import Q
        visits = visits.filter(Q(management_followup__isnull=False) | ~Q(admin_followup='')).distinct()

    visits = list(visits)
    for visit in visits:
        visit.followed = _is_followed(visit)

    return render(request, 'school/supervisor_visits_report.html', {
        'visits': visits,
        'info': SchoolInfo.objects.first(),
        'teachers': teachers,
        'selected_teacher_id': selected_teacher_id,
        'status': status,
        'can_followup': _can_followup(request.user),
    })
