from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from school.models import Class, Subject, Teacher
from .models import LearningLesson, LearningResource


def _role(request):
    try:
        return request.user.profile.role
    except Exception:
        return None


def _is_admin(request):
    return _role(request) == 'admin'


def _teacher_of(user):
    try:
        return user.teacher_profile
    except Teacher.DoesNotExist:
        return None


@login_required
def lesson_list(request):
    role = _role(request)
    status = request.GET.get('status', '')
    lessons = LearningLesson.objects.select_related('student_class', 'subject', 'teacher')

    if role == 'student':
        student = request.user.student_profile
        lessons = lessons.filter(student_class=student.student_class, status='published')
    elif role == 'teacher':
        teacher = _teacher_of(request.user)
        if not teacher:
            messages.error(request, 'لا يوجد ملف معلم مرتبط بهذا الحساب')
            return redirect('home')
        lessons = lessons.filter(teacher=teacher)
    else:
        if status in dict(LearningLesson.STATUS_CHOICES):
            lessons = lessons.filter(status=status)

    statuses = [{'key': s, 'label': l} for s, l in LearningLesson.STATUS_CHOICES]
    return render(request, 'open_learning/lesson_list.html', {
        'lessons': lessons,
        'role': role,
        'is_admin': _is_admin(request),
        'current_status': status,
        'statuses': statuses,
    })


@login_required
def lesson_add(request):
    role = _role(request)
    if role == 'student':
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    teacher = _teacher_of(request.user)
    if role == 'teacher' and not teacher:
        messages.error(request, 'لا يوجد ملف معلم مرتبط بهذا الحساب')
        return redirect('home')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        student_class = request.POST.get('student_class', '')
        subject = request.POST.get('subject', '')
        if not title or not student_class or not subject:
            messages.error(request, 'يرجى تعبئة العنوان والصف والمادة')
        else:
            student_class_obj = Class.objects.filter(pk=student_class).first()
            subject_obj = Subject.objects.filter(pk=subject).first()
            if not student_class_obj or not subject_obj:
                messages.error(request, 'الصف أو المادة غير موجود')
            elif role == 'teacher' and (student_class_obj not in teacher.classes.all() or subject_obj not in teacher.subjects.all()):
                messages.error(request, 'يمكنك الإضافة لصفوفك وموادك فقط')
            else:
                lesson = LearningLesson.objects.create(
                    title=title,
                    description=description,
                    student_class=student_class_obj,
                    subject=subject_obj,
                    teacher=teacher if role == 'teacher' else Teacher.objects.filter(pk=request.POST.get('teacher', '')).first(),
                    status='draft',
                )
                messages.success(request, 'تم إنشاء الدرس كمسودة. أرسله للاعتماد عند الانتهاء.')
                return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

    if role == 'teacher':
        classes = teacher.classes.all()
        subjects = teacher.subjects.all()
        teachers = Teacher.objects.none()
        if not classes.exists():
            messages.warning(request, 'لا توجد صفوف مرتبطة بحسابك. تواصل مع المدير.')
        if not subjects.exists():
            messages.warning(request, 'لا توجد مواد مرتبطة بحسابك. تواصل مع المدير.')
    else:
        classes = Class.objects.all()
        subjects = Subject.objects.all()
        teachers = Teacher.objects.all()

    return render(request, 'open_learning/lesson_form.html', {
        'lesson': None,
        'classes': classes,
        'subjects': subjects,
        'teachers': teachers,
        'role': role,
    })


def _can_manage(request, lesson):
    role = _role(request)
    if _is_admin(request):
        return True
    teacher = _teacher_of(request.user)
    return teacher is not None and lesson.teacher_id == teacher.pk


@login_required
def lesson_edit(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية لتعديل هذا الدرس')
        return redirect('open_learning_list')
    if lesson.status in ('published', 'pending'):
        messages.warning(request, 'لا يمكن تعديل الدرس في حالته الحالية')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
    role = _role(request)
    teacher = _teacher_of(request.user)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        student_class = Class.objects.filter(pk=request.POST.get('student_class', '')).first()
        subject = Subject.objects.filter(pk=request.POST.get('subject', '')).first()
        if not title or not student_class or not subject:
            messages.error(request, 'يرجى تعبئة العنوان والصف والمادة')
        elif role == 'teacher' and (student_class not in teacher.classes.all() or subject not in teacher.subjects.all()):
            messages.error(request, 'يمكنك التعديل ضمن صفوفك وموادك فقط')
        else:
            lesson.title = title
            lesson.description = description
            lesson.student_class = student_class
            lesson.subject = subject
            lesson.status = 'draft'
            lesson.review_note = ''
            lesson.save()
            messages.success(request, 'تم تحديث الدرس وأصبح مسودة')
            return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)

    if role == 'teacher':
        classes = teacher.classes.all()
        subjects = teacher.subjects.all()
    else:
        classes = Class.objects.all()
        subjects = Subject.objects.all()
    return render(request, 'open_learning/lesson_form.html', {
        'lesson': lesson,
        'classes': classes,
        'subjects': subjects,
        'role': role,
    })


@login_required
def lesson_delete(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية لحذف هذا الدرس')
        return redirect('open_learning_list')
    if request.method == 'POST':
        lesson.delete()
        messages.success(request, 'تم حذف الدرس')
        return redirect('open_learning_list')
    return render(request, 'open_learning/lesson_delete.html', {'lesson': lesson})


@login_required
def lesson_submit(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    if lesson.status not in ('draft', 'rejected'):
        messages.warning(request, 'الدرس غير قابل للإرسال في حالته الحالية')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
    if not lesson.resources.exists():
        messages.error(request, 'أضف مورداً تعليمياً واحداً على الأقل قبل إرسال الدرس للاعتماد')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
    lesson.status = 'pending'
    lesson.review_note = ''
    lesson.save()
    messages.success(request, 'أُرسل الدرس لانتظار اعتماد المدير')
    return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)


@login_required
def lesson_approve(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _is_admin(request):
        messages.error(request, 'الاعتماد من صلاحيات مدير المدرسة فقط')
        return redirect('open_learning_list')
    if lesson.status == 'pending':
        lesson.status = 'approved'
        lesson.reviewed_by = request.user
        lesson.save()
        messages.success(request, 'تم اعتماد الدرس. نشره الآن للطلاب عند الرغبة.')
    else:
        messages.warning(request, 'لا يمكن الاعتماد في الحالة الحالية')
    return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)


@login_required
def lesson_publish(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _is_admin(request):
        messages.error(request, 'النشر من صلاحيات مدير المدرسة فقط')
        return redirect('open_learning_list')
    if lesson.status == 'approved':
        lesson.status = 'published'
        lesson.reviewed_by = request.user
        lesson.save()
        messages.success(request, 'تم نشر الدرس وسيظهر للطلاب')
    else:
        messages.warning(request, 'لا يمكن النشر في الحالة الحالية')
    return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)


@login_required
def lesson_reject(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _is_admin(request):
        messages.error(request, 'الرفض من صلاحيات مدير المدرسة فقط')
        return redirect('open_learning_list')
    if request.method == 'POST':
        note = request.POST.get('review_note', '').strip()
        lesson.status = 'rejected'
        lesson.reviewed_by = request.user
        lesson.review_note = note
        lesson.save()
        messages.success(request, 'تم رفض الدرس مع إشعار المعلم بالملاحظة')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
    return render(request, 'open_learning/lesson_reject.html', {'lesson': lesson})


@login_required
def lesson_archive(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _is_admin(request):
        messages.error(request, 'الأرشفة من صلاحيات مدير المدرسة فقط')
        return redirect('open_learning_list')
    if lesson.status in ('published', 'approved'):
        lesson.status = 'archived'
        lesson.save()
        messages.success(request, 'تمت أرشفة الدرس ولم يعد ظاهراً للطلاب')
    else:
        messages.warning(request, 'لا يمكن الأرشفة في الحالة الحالية')
    return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)


@login_required
def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(
        LearningLesson.objects.select_related('student_class', 'subject', 'teacher').prefetch_related('resources'),
        pk=lesson_id,
    )
    role = _role(request)
    if role == 'student':
        student = request.user.student_profile
        if lesson.student_class_id != student.student_class_id or lesson.status != 'published':
            messages.error(request, 'لا يمكنك الاطلاع على هذا الدرس')
            return redirect('open_learning_list')
    elif role == 'teacher' and not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')

    can_manage = _can_manage(request, lesson)
    if role == 'student':
        visible_resources = lesson.resources.filter(status='approved')
    else:
        visible_resources = lesson.resources.all()
    return render(request, 'open_learning/lesson_detail.html', {
        'lesson': lesson,
        'role': role,
        'is_admin': _is_admin(request),
        'can_manage': can_manage,
        'ai_visible': lesson.ai_visible_to_students,
        'visible_resources': visible_resources,
    })


@login_required
def resource_add(request, lesson_id):
    lesson = get_object_or_404(LearningLesson, pk=lesson_id)
    if not _can_manage(request, lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    if lesson.status in ('published', 'pending'):
        messages.warning(request, 'لا يمكن إضافة موارد في الحالة الحالية')
        return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        resource_type = request.POST.get('resource_type', '')
        url = request.POST.get('url', '').strip()
        description = request.POST.get('description', '').strip()
        valid_types = dict(LearningResource.RESOURCE_TYPES)
        if not title or not url:
            messages.error(request, 'يرجى تعبئة العنوان والرابط')
        elif resource_type not in valid_types:
            messages.error(request, 'نوع المورد غير صحيح')
        else:
            LearningResource.objects.create(
                lesson=lesson,
                title=title,
                resource_type=resource_type,
                url=url,
                description=description,
            )
            messages.success(request, 'تمت إضافة المورد')
            return redirect('open_learning_lesson_detail', lesson_id=lesson.pk)
    return render(request, 'open_learning/resource_form.html', {
        'lesson': lesson,
        'resource_types': LearningResource.RESOURCE_TYPES,
    })


@login_required
def resource_delete(request, lesson_id, resource_id):
    resource = get_object_or_404(LearningResource, pk=resource_id, lesson_id=lesson_id)
    if not _can_manage(request, resource.lesson):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('open_learning_list')
    resource.delete()
    messages.success(request, 'تم حذف المورد')
    return redirect('open_learning_lesson_detail', lesson_id=lesson_id)
