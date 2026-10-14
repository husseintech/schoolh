"""Printable school follow-up registers and frequent-absence reports."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .arabic_sort import arabic_sort_key
from .attendance_register import (
    DEFAULT_REGISTER_STUDENTS,
    MAX_REGISTER_STUDENTS,
    MIN_REGISTER_STUDENTS,
    academic_year_start,
    normalize_row_count,
    normalize_start_year,
)
from .models import (
    Class,
    SchoolInfo,
    Student,
    StudentAbsence,
    Teacher,
    TeacherScheduleEntry,
    has_perm,
)


def _teacher_for_request(request, teacher_id=""):
    """Teachers can only build their own books; administrators may select a teacher."""
    role = request.user.profile.role
    if role == "teacher":
        return getattr(request.user, "teacher_profile", None)
    if role == "admin":
        if teacher_id and str(teacher_id).isdigit():
            return Teacher.objects.filter(pk=int(teacher_id)).first()
        return None
    return None


def _classes_for_teacher(teacher):
    if not teacher:
        return Class.objects.none()
    class_ids = set(teacher.classes.values_list("pk", flat=True))
    class_ids.update(
        TeacherScheduleEntry.objects.filter(
            teacher=teacher, student_class__isnull=False
        ).values_list("student_class_id", flat=True)
    )
    guardian_class = getattr(teacher, "guardian_class", None)
    if guardian_class:
        class_ids.add(guardian_class.pk)
    return Class.objects.filter(pk__in=class_ids).order_by("name", "pk")


@login_required
def frequent_absence_report(request):
    if not has_perm(request.user, "absence", "view"):
        messages.error(request, "ليس لديك صلاحية")
        return redirect("dashboard")

    try:
        threshold = int(request.GET.get("threshold", "10"))
    except (TypeError, ValueError):
        threshold = 10
    threshold = max(1, min(threshold, 100))

    year_start = academic_year_start(timezone.localdate())
    year_begin = date(year_start, 8, 1)
    year_end = date(year_start + 1, 7, 31)
    try:
        requested_start = date.fromisoformat(request.GET.get("start", ""))
        if requested_start:
            year_begin = requested_start
    except (TypeError, ValueError):
        pass
    try:
        requested_end = date.fromisoformat(request.GET.get("end", ""))
        if requested_end:
            year_end = requested_end
    except (TypeError, ValueError):
        pass
    if year_end < year_begin:
        year_begin, year_end = year_end, year_begin

    students = list(
        Student.objects.select_related("student_class")
        .filter(
            absences__absence_date__gte=year_begin,
            absences__absence_date__lte=year_end,
        )
        .annotate(absence_count=Count("absences", distinct=True))
        .filter(absence_count__gt=threshold)
        .order_by("student_class__name", "full_name", "pk")
        .prefetch_related(
            Prefetch(
                "absences",
                queryset=StudentAbsence.objects.filter(
                    absence_date__gte=year_begin,
                    absence_date__lte=year_end,
                ).order_by("absence_date"),
                to_attr="report_absences",
            )
        )
    )
    weekdays = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")
    rows = []
    for index, student in enumerate(students, start=1):
        absence_days = [
            {
                "date": item.absence_date,
                "day": weekdays[item.absence_date.weekday()],
            }
            for item in student.report_absences
        ]
        rows.append({
            "number": index,
            "student": student,
            "class_name": student.student_class.name if student.student_class else "بدون صف",
            "count": student.absence_count,
            "days": absence_days,
        })

    return render(request, "school/frequent_absence_report.html", {
        "rows": rows,
        "threshold": threshold,
        "start_date": year_begin,
        "end_date": year_end,
        "academic_year": f"{year_start}/{year_start + 1}",
        "total_students": len(rows),
        "today": timezone.localdate(),
    })


def _parse_followup_criteria(post_data):
    names = post_data.getlist("criterion_name")
    weights = post_data.getlist("criterion_weight")
    criteria = []
    errors = []
    for index, raw_name in enumerate(names):
        name = raw_name.strip()
        raw_weight = weights[index].strip() if index < len(weights) else ""
        if not name and not raw_weight:
            continue
        if not name:
            errors.append(f"البند رقم {index + 1}: أدخل اسم البند.")
            continue
        try:
            weight = Decimal(raw_weight or "0")
        except InvalidOperation:
            errors.append(f"البند «{name}»: الوزن يجب أن يكون رقمًا.")
            continue
        if weight < 0 or weight > 100:
            errors.append(f"البند «{name}»: الوزن يجب أن يكون بين 0 و100%.")
            continue
        criteria.append({"name": name, "weight": weight})
    if not criteria:
        errors.append("أدخل بند متابعة واحدًا على الأقل.")
    if len(criteria) > 12:
        errors.append("الحد الأقصى 12 بندًا حتى تبقى أعمدة الدفتر واضحة عند الطباعة.")
    return criteria, errors


def _followup_print_context(request, teacher, classes, criteria, row_count, start_year):
    class_pages = []
    for cls in classes:
        students = list(
            Student.objects.filter(student_class=cls).order_by("display_order", "full_name", "pk")
        )
        # Match the school's established register ordering while retaining the Excel display order.
        students = sorted(
            students,
            key=lambda student: (
                student.display_order if student.display_order > 0 else 2147483647,
                arabic_sort_key(student.full_name),
                student.pk,
            ),
        )
        student_rows = []
        for number in range(1, row_count + 1):
            student_rows.append({
                "number": number,
                "name": students[number - 1].full_name if number <= len(students) else "",
            })
        class_pages.append({
            "class": cls,
            "class_name": cls.name,
            "student_rows": student_rows,
            "student_count": len(students),
            "students_omitted": max(0, len(students) - row_count),
        })
    return {
        "selected_teacher": teacher,
        "class_pages": class_pages,
        "criteria": criteria,
        "row_count": row_count,
        "row_height": f"{155 / row_count:.3f}",
        "start_year": start_year,
        "academic_year": f"{start_year}/{start_year + 1}",
        "info": SchoolInfo.objects.first(),
        "total_weight": sum((item["weight"] for item in criteria), Decimal("0")),
    }


@login_required
def followup_register(request):
    role = request.user.profile.role
    if role not in ("admin", "teacher"):
        messages.error(request, "ليس لديك صلاحية للوصول إلى دفتر المتابعة")
        return redirect("dashboard")

    teachers = Teacher.objects.all().order_by("full_name") if role == "admin" else []
    teacher_id = request.POST.get("teacher_id", "") if request.method == "POST" else request.GET.get("teacher", "")
    teacher = _teacher_for_request(request, teacher_id)
    available_classes = _classes_for_teacher(teacher)
    row_count = normalize_row_count(
        request.POST.get("row_count") if request.method == "POST" else request.GET.get("rows")
    )
    start_year = normalize_start_year(
        request.POST.get("year") if request.method == "POST" else request.GET.get("year")
    )

    if request.method == "POST":
        action = request.POST.get("action", "print")
        if not teacher:
            messages.error(request, "اختر المعلم أولًا.")
            return redirect("followup_register")
        selected_ids = []
        for raw_id in request.POST.getlist("class_ids"):
            if raw_id.isdigit() and int(raw_id) not in selected_ids:
                selected_ids.append(int(raw_id))
        allowed_ids = set(available_classes.values_list("pk", flat=True))
        selected_ids = [class_id for class_id in selected_ids if class_id in allowed_ids]
        classes_by_id = {cls.pk: cls for cls in available_classes.filter(pk__in=selected_ids)}
        selected_classes = [classes_by_id[class_id] for class_id in selected_ids if class_id in classes_by_id]
        if not selected_classes:
            messages.error(request, "حدد شعبة أو صفًا واحدًا على الأقل.")
            return redirect(f"/teachers/followup-register/?teacher={teacher.pk}" if role == "admin" else "followup_register")

        criteria, errors = _parse_followup_criteria(request.POST)
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, "school/followup_register.html", {
                "teachers": teachers,
                "selected_teacher": teacher,
                "available_classes": available_classes,
                "selected_class_ids": set(selected_ids),
                "criteria_form_rows": [
                    {"name": name, "weight": weight}
                    for name, weight in zip(
                        request.POST.getlist("criterion_name"),
                        request.POST.getlist("criterion_weight"),
                    )
                ],
                "row_count": row_count,
                "row_options": range(MIN_REGISTER_STUDENTS, MAX_REGISTER_STUDENTS + 1),
                "start_year": start_year,
                "default_criteria": False,
            })

        context = _followup_print_context(request, teacher, selected_classes, criteria, row_count, start_year)
        context["print_cover_only"] = action == "cover"
        template = "school/followup_register_cover.html" if action == "cover" else "school/followup_register_print.html"
        return render(request, template, context)

    criteria_form_rows = [{"name": "", "weight": ""}]
    return render(request, "school/followup_register.html", {
        "teachers": teachers,
        "selected_teacher": teacher,
        "available_classes": available_classes,
        "selected_class_ids": set(),
        "criteria_form_rows": criteria_form_rows,
        "row_count": row_count,
        "row_options": range(MIN_REGISTER_STUDENTS, MAX_REGISTER_STUDENTS + 1),
        "start_year": start_year,
        "default_criteria": True,
    })
