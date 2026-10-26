import json
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import escape

from .models import Class, ExamFont, ExamPaper, SchoolInfo, Subject, Teacher, TeacherScheduleEntry


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
    exam_fonts = ExamFont.objects.all()
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
        exam_direction = request.POST.get("exam_direction", "rtl")
        if exam_direction not in ("rtl", "ltr"):
            exam_direction = "rtl"
        if exam_type == "اختبار مخصص":
            exam_type = request.POST.get("exam_type_custom", "").strip()[:100] or "اختبار مخصص"
        duration_raw = request.POST.get("duration", "40")
        font_name = request.POST.get("font_name", "Traditional Arabic")[:80]
        font_size_raw = request.POST.get("font_size", "16")
        header_font_size_raw = request.POST.get("header_font_size", "9")
        header_font_weight_raw = request.POST.get("header_font_weight", "400")
        header_font_family = request.POST.get("header_font_family", "Traditional Arabic")[:80]
        header_text_align = request.POST.get("header_text_align", "center")
        header_line_height_raw = request.POST.get("header_line_height", "1.3")
        header_letter_spacing_raw = request.POST.get("header_letter_spacing", "0")
        header_padding_raw = request.POST.get("header_padding", "0")
        header_left_offset_raw = request.POST.get("header_left_offset", "0")
        header_right_offset_raw = request.POST.get("header_right_offset", "0")
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
            number = str(question.get("number", "")).strip()[:20]
            if not number:
                messages.error(request, "رقم السؤال إجباري. يرجى إدخال رقم لكل سؤال.")
                return redirect("exam_writer")
            display_number = number
            safe_questions.append({
                "type": kind,
                "text": text,
                "marks": marks,
                "lines": lines,
                "number": number,
                "display_number": display_number,
                "choices": [str(x)[:1000] for x in choices[:6]],
                "left": str(question.get("left", ""))[:5000],
                "right": str(question.get("right", ""))[:5000],
                "images": [
                    {
                        "src": str(image.get("src", ""))[:2200000],
                        "width": max(10, min(90, int(image.get("width", 40) or 40))),
                        "x": max(-2000, min(2000, int(image.get("x", 0) or 0))),
                        "y": max(-2000, min(2000, int(image.get("y", 0) or 0))),
                    }
                    for image in question.get("images", [])[:10]
                    if isinstance(image, dict) and str(image.get("src", "")).startswith("data:image/")
                ] if isinstance(question.get("images", []), list) else (
                    [{"src": str(question.get("image", ""))[:2200000],
                      "width": max(10, min(90, int(question.get("imageWidth", 40) or 40))),
                      "x": 0, "y": 0}]
                    if str(question.get("image", "")).startswith("data:image/") else []
                ),
                "table": [[str(cell)[:500] for cell in row[:10]] for row in question.get("table", [])[:20] if isinstance(row, list)] if isinstance(question.get("table", []), list) else [],
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
        paper.exam_direction = exam_direction
        paper.questions = safe_questions
        paper.font_name = font_name
        paper.font_size = max(10, min(24, font_size))
        paper.header_font_size = max(7, min(14, header_font_size))
        paper.header_font_weight = header_font_weight if header_font_weight in (300, 400, 600, 700, 900) else 400
        paper.header_font_family = header_font_family
        paper.header_text_align = header_text_align if header_text_align in ("left", "center", "right") else "center"
        paper.header_line_height = max(1, min(2, header_line_height))
        paper.header_letter_spacing = max(0, min(3, header_letter_spacing))
        paper.header_padding = max(0, min(16, header_padding))
        paper.header_left_offset = max(-150, min(150, int(header_left_offset_raw or 0)))
        paper.header_right_offset = max(-150, min(150, int(header_right_offset_raw or 0)))
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
        "exam_fonts": exam_fonts,
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
    is_english_subject = paper.exam_direction == "ltr"
    response = render(request, "school/exam_paper_print.html", {
        "paper": paper,
        "school_info": school_info,
        "word_export": request.GET.get("format") == "word",
        "exam_fonts": ExamFont.objects.all(),
        "is_english_subject": is_english_subject,
    })
    if request.GET.get("format") == "word":
        response["Content-Type"] = "application/msword; charset=utf-8"
        response["Content-Disposition"] = 'attachment; filename="school-exam.doc"'
    return response


@login_required
def exam_font_upload(request):
    if request.method != "POST":
        return redirect("exam_writer")
    if _role(request.user) != "admin":
        return HttpResponseForbidden("رفع الخطوط متاح للإدارة فقط.")
    uploaded = request.FILES.get("font_file")
    name = request.POST.get("font_display_name", "").strip()[:100]
    if not uploaded or not name:
        messages.error(request, "أدخل اسم الخط واختر ملفًا لرفعه.")
        return redirect("exam_writer")
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in (".ttf", ".otf", ".woff", ".woff2"):
        messages.error(request, "صيغة الخط غير مدعومة. استخدم TTF أو OTF أو WOFF أو WOFF2.")
        return redirect("exam_writer")
    if uploaded.size > 5 * 1024 * 1024:
        messages.error(request, "حجم ملف الخط يجب ألا يتجاوز 5 ميغابايت.")
        return redirect("exam_writer")
    font, created = ExamFont.objects.get_or_create(name=name, defaults={"file": uploaded, "uploaded_by": request.user})
    if not created:
        messages.error(request, "يوجد خط بهذا الاسم بالفعل. اختر اسمًا آخر.")
        return redirect("exam_writer")
    messages.success(request, "تم رفع الخط وحفظه في مكتبة خطوط الاختبارات.")
    return redirect("exam_writer")


@login_required
def exam_paper_delete(request, paper_id):
    if request.method != "POST":
        return redirect("exam_writer")
    paper = get_object_or_404(ExamPaper.objects.select_related("teacher"), pk=paper_id)
    if _role(request.user) != "admin" and paper.teacher.user_id != request.user.id:
        return HttpResponseForbidden("ليس لديك صلاحية حذف هذا الاختبار.")
    teacher_id = paper.teacher_id
    paper_name = paper.exam_name
    paper.delete()
    messages.success(request, f"تم حذف الاختبار «{paper_name}».")
    if _role(request.user) == "admin":
        return redirect(f"{reverse('exam_writer')}?teacher_id={teacher_id}")
    return redirect("exam_writer")
