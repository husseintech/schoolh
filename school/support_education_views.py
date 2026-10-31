from datetime import date
import logging
from django.db import connection
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.dateparse import parse_date
from .models import Profile, Teacher, Class, UserPermission, SupportLessonAssignment, SupportLessonExecution, has_perm

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
    if request.method == 'POST' and request.POST.get('teacher_id'):
        existing = get_object_or_404(Teacher, pk=request.POST.get('teacher_id'), user__profile__role='support_teacher')
        existing.support_classes.set(Class.objects.filter(pk__in=request.POST.getlist('support_classes')))
        messages.success(request, 'تم تحديث الصفوف المكلف بها المعلم المساند')
        return redirect('support_teacher_manage')
    if request.method == 'POST':
        name = request.POST.get('full_name', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        specialization = request.POST.get('specialization', '').strip()
        class_ids = request.POST.getlist('support_classes')
        if not all([name, username, password, specialization]):
            messages.error(request, 'يرجى إدخال الاسم والتخصص واسم المستخدم وكلمة المرور')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'اسم المستخدم مستخدم مسبقاً')
        else:
            user = User.objects.create_user(username=username, password=password, first_name=name)
            Profile.objects.create(user=user, role='support_teacher')
            UserPermission.objects.create(user=user, permissions={})
            support_profile = Teacher.objects.create(user=user, full_name=name, specialization=specialization)
            support_profile.support_classes.set(Class.objects.filter(pk__in=class_ids))
            messages.success(request, 'تم إنشاء حساب المعلم المساند وحفظ الصفوف المكلف بها')
            return redirect('support_teacher_manage')
    teachers = Teacher.objects.filter(user__profile__role='support_teacher').select_related('user').order_by('full_name')
    return render(request, 'school/support_teacher_manage.html', {'support_teachers': teachers, 'classes': Class.objects.all().order_by('name')})

@login_required
def support_assignment_list(request):
    if _role(request.user) != 'teacher':
        messages.error(request, 'تسجيل التكليفات متاح للمعلم الأصيل فقط')
        return redirect('support_dashboard')
    teacher = get_object_or_404(Teacher, user=request.user)
    classes = teacher.classes.all()
    assignments = SupportLessonAssignment.objects.filter(original_teacher=teacher).select_related('class_obj').prefetch_related('executions__support_teacher')
    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        class_obj = get_object_or_404(classes, pk=class_id)
        title = request.POST.get('lesson_title', '').strip()
        page = request.POST.get('page_number', '').strip()
        required = request.POST.get('required_work', '').strip()
        if not title or not required:
            messages.error(request, 'عنوان الدرس والمطلوب تنفيذه حقول مطلوبة')
        else:
            SupportLessonAssignment.objects.create(class_obj=class_obj, original_teacher=teacher, lesson_title=title, page_number=page, required_work=required)
            messages.success(request, 'تم حفظ التكليف، وبقيت التكليفات السابقة محفوظة')
            return redirect('support_assignment_list')
    return render(request, 'school/support_assignment_list.html', {'classes': classes, 'assignments': assignments})

@login_required
def support_dashboard(request):
    if _support_teacher(request.user):
        teacher = request.user.teacher_profile
        selected_id = request.GET.get('class_id', '')
        classes = teacher.support_classes.all().order_by('name')
        selected = get_object_or_404(classes, pk=selected_id) if selected_id else None
        assignment = SupportLessonAssignment.objects.filter(class_obj=selected).select_related('original_teacher').first() if selected else None
        executions = SupportLessonExecution.objects.filter(support_teacher=teacher).select_related('assignment__class_obj','assignment__original_teacher')
        if request.method == 'POST':
            assignment_id = request.POST.get('assignment_id')
            target = get_object_or_404(SupportLessonAssignment, pk=assignment_id, class_obj__in=classes)
            if not request.POST.get('execution_date') or not request.POST.get('lesson_period') or not request.POST.get('notes','').strip():
                messages.error(request, 'يرجى إدخال تاريخ التنفيذ ورقم الحصة والمتابعة')
            else:
                execution_date = parse_date(request.POST['execution_date'])
                try:
                    lesson_period = int(request.POST['lesson_period'])
                except (TypeError, ValueError):
                    lesson_period = 0
                if not execution_date or not 1 <= lesson_period <= 12:
                    messages.error(request, 'تاريخ التنفيذ أو رقم الحصة غير صحيح')
                    return redirect('/support-education/?class_id=%s' % target.class_obj_id)
                SupportLessonExecution.objects.create(assignment=target, support_teacher=teacher, execution_date=execution_date, lesson_period=lesson_period, notes=request.POST['notes'].strip())
                messages.success(request, 'تم تسجيل متابعة التنفيذ دون تعديل تكليف المعلم الأصيل')
                return redirect('/support-education/?class_id=%s' % target.class_obj_id)
        return render(request, 'school/support_teacher_dashboard.html', {'classes': classes, 'selected_class': selected, 'assignment': assignment, 'executions': executions})
    if _role(request.user) not in ('admin', 'vice_principal', 'secretary'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    return redirect('support_reports')

@login_required
def support_reports(request):
    if _role(request.user) not in ('admin', 'vice_principal', 'secretary'):
        messages.error(request, 'ليس لديك صلاحية لعرض التقارير')
        return redirect('dashboard')
    # Temporary safe diagnostics: identify the database selected by this Vercel deployment
    # without logging credentials or connection strings.
    try:
        tables = set(connection.introspection.table_names())
        logger.error(
            "SUPPORT_EDU_DB_DIAGNOSTIC host=%s database=%s user=%s schema=%s "
            "assignment_table=%s execution_table=%s supabase_url_set=%s database_url_set=%s",
            connection.settings_dict.get('HOST'),
            connection.settings_dict.get('NAME'),
            connection.settings_dict.get('USER'),
            connection.settings_dict.get('OPTIONS', {}).get('options', ''),
            'school_supportlessonassignment' in tables,
            'school_supportlessonexecution' in tables,
            bool(__import__('os').environ.get('SUPABASE_DATABASE_URL')),
            bool(__import__('os').environ.get('DATABASE_URL')),
        )
    except Exception:
        logger.exception("SUPPORT_EDU_DB_DIAGNOSTIC_FAILED")
    qs = SupportLessonAssignment.objects.select_related('class_obj','original_teacher').prefetch_related('executions__support_teacher')
    class_id=request.GET.get('class_id',''); original_id=request.GET.get('original_teacher',''); support_id=request.GET.get('support_teacher','')
    start=parse_date(request.GET.get('from_date','')); end=parse_date(request.GET.get('to_date',''))
    if class_id: qs=qs.filter(class_obj_id=class_id)
    if original_id: qs=qs.filter(original_teacher_id=original_id)
    if support_id: qs=qs.filter(executions__support_teacher_id=support_id).distinct()
    if start: qs=qs.filter(created_at__date__gte=start)
    if end: qs=qs.filter(created_at__date__lte=end)
    return render(request, 'school/support_education_report.html', {'assignments':qs,'classes':Class.objects.all(),'original_teachers':Teacher.objects.filter(user__profile__role='teacher'),'support_teachers':Teacher.objects.filter(user__profile__role='support_teacher'),'filters':request.GET})
