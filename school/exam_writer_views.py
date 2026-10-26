import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import escape

from .models import Class, ExamPaper, SchoolInfo, Subject, Teacher, TeacherScheduleEntry


def _role(user):
    return getattr(getattr(user, "profile", None), "role", None)


def _teacher_classes(teacher):
    """Classes assigned directly to the teacher or present in their saved timetable."""
    direct_ids = set(teacher.classes.values_list("id", flat=True))
    scheduled_ids = set(
        TeacherScheduleEntry.objects.filter(
            teacher=teacher, student_class__isnull=False
        ).values_list("student_class_id", flat=True)
    )
    return Class.objects.filter(id__in=direct_ids | scheduled_ids).order_by("name")


def _teacher_subjects(teacher):
    direct_ids = set(teacher.subjects.values_list("id", flat=True))
    scheduled_ids = set(
        TeacherScheduleEntry.objects.filter(
            teacher=teacher, subject__isnull=False
        ).values_list("subject_id", flat=True)
    )
    return Subject.objects.filter(id__in=direct_ids | scheduled_ids).order_by("name")


def _teacher_for_request(request):
    if _role(request.user) == "teacher":
        return Teacher.objects.filter(user=request.user).first()
    teacher_id = request.POST.get("teacher_id") or request.GET.get("teacher_id")
    if teacher_id and str(teacher_id).isdigit():
        return Teacher.objects.filter(pk=int(teacher_id)).first()
    return None


@login_required
def exam_writer(request):
    role = _role(request.user)
    if role not in ("admin", "teacher"):
        messages.error(request, "أداة كتابة الاختبارات متاحة للمعلمين والإدارة فقط.")
        return redirect("dashboard")

    teacher = _teacher_for_request(request)
    if role == "teacher" and teacher is None:
        messages.error(request, "لا يوجد ملف معلم مرتبط بحسابك. يرجى مراجعة الإدارة.")
        return redirect("dashboard")

    teachers = Teacher.objects.order_by("full_name") if role == "admin" else []
    selected_classes = _teacher_classes(teacher) if teacher else Class.objects.none()
    selected_subjects = _teacher_subjects(teacher) if teacher else Subject.objects.none()
    school_info = SchoolInfo.objects.first()

    if request.method == "POST":
        if role == "admin":
            teacher_id = request.POST.get("teacher_id", "")
            teacher = Teacher.objects.filter(pk=teacher_id).first() if teacher_id.isdigit() else None
            if not teacher:
                messages.error(request, "اختر المعلم الذي سيُنسب إليه الاختبار.")
                return redirect("exam_writer")
            selected_classes = _teacher_classes(teacher)
            selected_subjects = _teacher_subjects(teacher)

        title = request.POST.get("exam_name", "").strip()
        subject_id = request.POST.get("subject_id", "")
        exam_type = request.POST.get("exam_type", "").strip()[:100]
        duration_raw = request.POST.get("duration", "40")
        font_name = request.POST.get("font_name", "Traditional Arabic")[:80]
        font_size_raw = request.POST.get("font_size", "16")
        class_ids = request.POST.getlist("class_ids")
        questions_raw = request.POST.get("questions_json", "[]")

        try:
            duration = int(duration_raw)
            font_size = int(font_size_raw)
            questions = json.loads(questions_raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            messages.error(request, "تعذر قراءة بعض بيانات الاختبار. راجع المدة والأسئلة ثم حاول مجددًا.")
            return redirect("exam_writer")

        valid_class_ids = set(selected_classes.filter(pk__in=class_ids).values_list("id", flat=True))
        subject = selected_subjects.filter(pk=subject_id).first()
        if not title or not subject or not valid_class_ids or duration < 1 or duration > 600:
            messages.error(request, "يرجى إدخال اسم الاختبار والمدة واختيار مبحث وشعبة واحدة على الأقل من الشعب المسندة للمعلم.")
            return redirect("exam_writer")
        if not isinstance(questions, list):
            messages.error(request, "صيغة الأسئلة غير صحيحة.")
            return redirect("exam_writer")

        safe_questions = []
        for question in questions[:100]:
            if not isinstance(question, dict):
                continue
            kind = str(question.get("type", "مقالي"))[:40]
            text = str(question.get("text", ""))[:10000]
            try:
                marks = max(0, min(1000, float(question.get("marks") or 0)))
            except (TypeError, ValueError):
                marks = 0
            try:
                lines = max(1, min(20, int(question.get("lines") or 3)))
            except (TypeError, ValueError):
                lines = 3
            choices = question.get("choices", [])
            if not isinstance(choices, list):
                choices = []
            safe_questions.append({
                "type": kind,
                "text": text,
                "marks": marks,
                "lines": lines,
                "choices": [str(x)[:1000] for x in choices[:6]],
                "left": str(question.get("left", ""))[:5000],
                "right": str(question.get("right", ""))[:5000],
            })

        paper_id = request.POST.get("paper_id", "")
        paper = None
        if paper_id.isdigit():
            paper = ExamPaper.objects.filter(pk=int(paper_id), teacher=teacher).first()
        if paper is None:
            paper = ExamPaper(teacher=teacher, created_by=request.user)
        paper.exam_name = title
        paper.subject = subject
        paper.duration_minutes = duration
        paper.exam_type = exam_type
        paper.questions = safe_questions
        paper.font_name = font_name
        paper.font_size = max(10, min(24, font_size))
        paper.save()
        paper.classes.set(valid_class_ids)
        messages.success(request, "تم حفظ الاختبار. يمكنك معاينته وطباعته أو تصديره إلى Word.")
        return redirect("exam_writer_edit", paper_id=paper.pk)

    papers = ExamPaper.objects.filter(teacher=teacher).select_related("subject").prefetch_related("classes") if teacher else ExamPaper.objects.none()
    edit_id = request.GET.get("edit")
    editing = None
    if edit_id and str(edit_id).isdigit():
        editing = papers.filter(pk=int(edit_id)).first()
    return render(request, "school/exam_writer.html", {
        "teachers": teachers,
        "teacher": teacher,
        "classes": selected_classes,
        "subjects": selected_subjects,
        "school_info": school_info,
        "papers": papers[:50],
        "editing": editing,
        "editing_class_ids": set(editing.classes.values_list("id", flat=True)) if editing else set(),
    })


@login_required
def exam_writer_edit(request, paper_id):
    paper = get_object_or_404(ExamPaper.objects.select_related("teacher", "subject").prefetch_related("classes"), pk=paper_id)
    if _role(request.user) != "admin" and paper.teacher.user_id != request.user.id:
        return HttpResponseForbidden("ليس لديك صلاحية الوصول إلى هذا الاختبار.")
    if _role(request.user) == "admin":
        return redirect(f"{reverse('exam_writer')}?edit={paper.pk}&teacher_id={paper.teacher_id}")
    return redirect(f"{reverse('exam_writer')}?edit={paper.pk}")


@login_required
def exam_paper_print(request, paper_id):
    paper = get_object_or_404(ExamPaper.objects.select_related("teacher", "subject").prefetch_related("classes"), pk=paper_id)
    if _role(request.user) != "admin" and paper.teacher.user_id != request.user.id:
        return HttpResponseForbidden("ليس لديك صلاحية الوصول إلى هذا الاختبار.")
    school_info = SchoolInfo.objects.first()
    response = render(request, "school/exam_paper_print.html", {
        "paper": paper,
        "school_info": school_info,
        "word_export": request.GET.get("format") == "word",
    })
    if request.GET.get("format") == "word":
        response["Content-Type"] = "application/msword; charset=utf-8"
        response["Content-Disposition"] = 'attachment; filename="school-exam.doc"'
    return response
