from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from school.models import Class, Subject, Teacher
from .models import (
    LearningLesson,
    WeeklyPlan,
    WeeklyPlanDay,
    WeeklyPlanReview,
    WeeklyPlanReviewItem,
    PLAN_WEEKDAYS,
    QUALITY_AXES,
)
from .views import _role, _is_admin, _teacher_of
from .google_drive import GoogleDriveService


def _arabic_weekday(d):
    return {7: 'الأحد', 1: 'الاثنين', 2: 'الثلاثاء', 3: 'الأربعاء', 4: 'الخميس', 5: 'الجمعة', 6: 'السبت'}.get(d.isoweekday(), '')


def _generate_days(plan):
    d = plan.week_start
    order = 0
    while d <= plan.week_end:
        name = _arabic_weekday(d)
        if name in PLAN_WEEKDAYS:
            WeeklyPlanDay.objects.get_or_create(
                weekly_plan=plan, date=d, defaults={'day_of_week': name, 'order': order}
            )
        order += 1
        d += timedelta(days=1)


def _plan_or_403(request, plan_id):
    plan = get_object_or_404(WeeklyPlan, pk=plan_id)
    role = _role(request)
    if role == 'student':
        return None, redirect('open_learning_list')
    if role == 'teacher':
        teacher = _teacher_of(request.user)
        if not teacher or plan.teacher_id != teacher.id:
            return None, redirect('open_learning_list')
    return plan, None


@login_required
def weekly_plan_list(request):
    role = _role(request)
    if role == 'student':
        messages.error(request, 'لا يمكنك الوصول إلى الخطط الأسبوعية')
        return redirect('open_learning_list')

    plans = WeeklyPlan.objects.select_related('teacher', 'student_class')
    filters = {}
    if role == 'teacher':
        teacher = _teacher_of(request.user)
        plans = plans.filter(teacher=teacher)
    else:
        t_id = request.GET.get('teacher')
        c_id = request.GET.get('class')
        w = request.GET.get('week')
        s = request.GET.get('status')
        if t_id:
            plans = plans.filter(teacher_id=t_id)
            filters['teacher'] = t_id
        if c_id:
            plans = plans.filter(student_class_id=c_id)
            filters['class'] = c_id
        if w:
            plans = plans.filter(week_start__lte=w, week_end__gte=w)
            filters['week'] = w
        if s in dict(WeeklyPlan.STATUS_CHOICES):
            plans = plans.filter(status=s)
            filters['status'] = s

    ctx = {
        'plans': plans,
        'role': role,
        'is_admin': _is_admin(request),
        'statuses': WeeklyPlan.STATUS_CHOICES,
        'filters': filters,
    }
    if role == 'admin':
        ctx['teachers'] = Teacher.objects.all()
        ctx['classes'] = Class.objects.all()
    return render(request, 'open_learning/weekly_plan_list.html', ctx)


@login_required
def weekly_plan_add(request):
    role = _role(request)
    if role == 'admin':
        messages.error(request, 'الخطط الأسبوعية يُنشئها المعلم فقط')
        return redirect('ol_weekly_plan_list')
    if role != 'teacher':
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    teacher = _teacher_of(request.user)
    if not teacher:
        messages.error(request, 'لا يوجد ملف معلم مرتبط بحسابك')
        return redirect('open_learning_list')

    classes = teacher.classes.all()
    if request.method == 'POST':
        class_id = request.POST.get('student_class')
        week_start = request.POST.get('week_start')
        student_class = Class.objects.filter(pk=class_id, teachers=teacher).first()
        if not student_class or not week_start:
            messages.error(request, 'يرجى تعبئة الصف وتاريخ بداية الأسبوع')
            return render(request, 'open_learning/weekly_plan_form.html', {'classes': classes})
        try:
            from datetime import datetime
            start = datetime.strptime(week_start, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'تاريخ غير صحيح')
            return render(request, 'open_learning/weekly_plan_form.html', {'classes': classes})
        end = start + timedelta(days=4)
        plan = WeeklyPlan.objects.create(
            teacher=teacher,
            student_class=student_class,
            week_start=start,
            week_end=end,
            delivery_mode=request.POST.get('delivery_mode') or 'presence',
        )
        _generate_days(plan)
        messages.success(request, 'تم إنشاء الخطة الأسبوعية')
        return redirect('ol_weekly_plan_detail', plan_id=plan.pk)
    return render(request, 'open_learning/weekly_plan_form.html', {'classes': classes})


@login_required
def weekly_plan_detail(request, plan_id):
    plan, err = _plan_or_403(request, plan_id)
    if err:
        return err
    role = _role(request)
    teacher = _teacher_of(request.user) if role == 'teacher' else None
    editable = (role == 'teacher' and teacher and plan.teacher_id == teacher.id and plan.is_editable)

    if request.method == 'POST' and editable:
        action = request.POST.get('action')
        if action == 'save':
            plan.delivery_mode = request.POST.get('delivery_mode') or plan.delivery_mode
            plan.save()
            for i, dow in enumerate(PLAN_WEEKDAYS):
                day = plan.days.filter(day_of_week=dow).first()
                if day is None:
                    day = WeeklyPlanDay(weekly_plan=plan, day_of_week=dow, order=i)
                date_val = request.POST.get(f'date_{i}') or (
                    plan.week_start + timedelta(days=i) if plan.week_start else None)
                subject = Subject.objects.filter(pk=request.POST.get(f'subject_{i}')).first() if request.POST.get(f'subject_{i}') else None
                lesson = LearningLesson.objects.filter(
                    pk=request.POST.get(f'lesson_{i}'), teacher=plan.teacher,
                    student_class=plan.student_class).first() if request.POST.get(f'lesson_{i}') else None
                day.date = date_val
                day.subject = subject
                day.lesson = lesson
                title = request.POST.get(f'lesson_title_{i}', '') or ''
                if lesson and not title:
                    title = lesson.title
                day.lesson_title = title
                day.objectives = request.POST.get(f'objectives_{i}', '') or ''
                day.homework = request.POST.get(f'homework_{i}', '') or ''
                day.notes = request.POST.get(f'notes_{i}', '') or ''
                day.task = request.POST.get(f'task_{i}', '') or ''
                day.task_due_date = request.POST.get(f'task_due_{i}') or None
                day.order = i
                day.save()
            messages.success(request, 'تم حفظ الخطة الأسبوعية')
        elif action == 'submit':
            plan.status = 'sent'
            plan.submitted_at = timezone_now()
            plan.save()
            messages.success(request, 'تم إرسال الخطة للمدير')
        return redirect('ol_weekly_plan_detail', plan_id=plan.pk)

    # GET or non-editable POST
    days = list(plan.days.all())
    days_by_dow = {d.day_of_week: d for d in days}
    week_rows = []
    for i, dow in enumerate(PLAN_WEEKDAYS):
        day = days_by_dow.get(dow)
        default_date = (plan.week_start + timedelta(days=i)) if plan.week_start else None
        week_rows.append({
            'dow': dow,
            'index': i,
            'day': day,
            'default_date': default_date,
            'is_empty': (day is None) or day.is_empty,
        })
    subjects = teacher.subjects.all() if teacher else Subject.objects.none()
    lessons = LearningLesson.objects.filter(teacher=plan.teacher, student_class=plan.student_class)
    review = plan.review if hasattr(plan, 'review') else None
    return render(request, 'open_learning/weekly_plan_detail.html', {
        'plan': plan,
        'week_rows': week_rows,
        'subjects': subjects,
        'lessons': lessons,
        'role': role,
        'is_admin': _is_admin(request),
        'editable': editable,
        'review': review,
    })


def _save_day(plan, request, day):
    lesson_id = request.POST.get('lesson')
    subject_id = request.POST.get('subject')
    lesson = LearningLesson.objects.filter(pk=lesson_id, teacher=plan.teacher, student_class=plan.student_class).first() if lesson_id else None
    subject = Subject.objects.filter(pk=subject_id).first() if subject_id else None
    if day is None:
        day = WeeklyPlanDay(weekly_plan=plan)
    day.day_of_week = request.POST.get('day_of_week', '')
    day.date = request.POST.get('date') or None
    day.subject = subject
    day.lesson = lesson
    if lesson:
        day.lesson_title = lesson.title
        if not day.objectives and lesson.ai_payload and lesson.ai_payload.get('objectives'):
            day.objectives = '\n'.join(lesson.ai_payload['objectives'])
    else:
        day.lesson_title = request.POST.get('lesson_title', '')
    day.objectives = request.POST.get('objectives', day.objectives)
    day.homework = request.POST.get('homework', '')
    day.notes = request.POST.get('notes', '')
    day.order = request.POST.get('order') or 0
    day.save()


@login_required
def weekly_plan_review(request, plan_id):
    if not _is_admin(request):
        messages.error(request, 'هذه الصفحة للمدير فقط')
        return redirect('ol_weekly_plan_list')
    plan = get_object_or_404(WeeklyPlan, pk=plan_id)
    review, _ = WeeklyPlanReview.objects.get_or_create(weekly_plan=plan)
    # Align review items with the current QUALITY_AXES (preserve existing answers)
    current_keys = {(a, i) for a, i in QUALITY_AXES}
    stored = list(review.items.all())
    stored_keys = {(it.axis, it.indicator) for it in stored}
    if stored_keys != current_keys:
        for it in stored:
            if (it.axis, it.indicator) not in current_keys:
                it.delete()
        for i, (axis, indicator) in enumerate(QUALITY_AXES):
            obj, created = WeeklyPlanReviewItem.objects.get_or_create(
                review=review, axis=axis, indicator=indicator,
                defaults={'order': i})
            if not created and obj.order != i:
                obj.order = i
                obj.save()

    from collections import OrderedDict
    items_map = {(it.axis, it.indicator): it for it in review.items.all()}
    groups = OrderedDict()
    for axis, indicator in QUALITY_AXES:
        groups.setdefault(axis, []).append(items_map[(axis, indicator)])
    axis_groups = list(groups.items())

    if request.method == 'POST':
        for item in review.items.all():
            is_met = request.POST.get(f'is_met_{item.id}') == 'on'
            needs = request.POST.get(f'needs_{item.id}') == 'on'
            if is_met and needs:
                needs = False
            item.is_met = is_met
            item.needs_improvement = needs
            item.note = request.POST.get(f'note_{item.id}', '')
            item.save()
        review.general_note = request.POST.get('general_note', '')
        result = request.POST.get('result', 'needs_improvement')
        review.status = result
        review.reviewed_by = request.user
        review.save()
        plan.status = 'reviewed' if result == 'approved' else 'needs_improvement'
        plan.reviewed_at = timezone_now()
        plan.save()
        messages.success(request, 'تم حفظ مراجعة الخطة')
        return redirect('ol_weekly_plan_detail', plan_id=plan.pk)

    return render(request, 'open_learning/weekly_plan_review.html', {
        'plan': plan,
        'review': review,
        'items': review.items.all(),
        'axis_groups': axis_groups,
        'is_admin': True,
        'role': _role(request),
    })


def timezone_now():
    from django.utils import timezone
    return timezone.now()


@login_required
def weekly_plan_delete(request, plan_id):
    plan, err = _plan_or_403(request, plan_id)
    if err:
        return err
    role = _role(request)
    if role == 'teacher':
        if not plan.is_editable:
            messages.error(request, 'لا يمكن حذف خطة مُرسلة أو مُراجَعة')
            return redirect('ol_weekly_plan_list')
    if request.method == 'POST':
        plan.delete()
        messages.success(request, 'تم حذف الخطة الأسبوعية')
    return redirect('ol_weekly_plan_list')
