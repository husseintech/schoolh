"""Printable school follow-up registers and frequent-absence reports."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import Count, Prefetch
from django.core.management import call_command
import logging
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
logger = logging.getLogger(__name__)

from .models import (
    Class,
    SchoolInfo,
    Student,
    StudentAbsence,
    Teacher,
    TeacherScheduleEntry,
    TeacherFollowupRegisterSettings,
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


def _followup_print_context(request, teacher, classes, criteria, row_count, start_year, semesters=(1, 2)):
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
            "semesters": [{"number": number, "label": "الفصل الأول" if number == 1 else "الفصل الثاني"} for number in semesters],
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

    # The Vercel entry point runs migrations at startup but historically swallowed
    # migration errors. Heal the specific settings migration here if the table is
    # missing, so this page can recover without touching student records.
    settings_table_ready = True
    saved_settings = None
    if teacher:
        try:
            table_name = TeacherFollowupRegisterSettings._meta.db_table
            with connection.cursor() as cursor:
                table_exists = table_name in connection.introspection.table_names(cursor)
            if not table_exists:
                call_command(
                    "migrate", "school", "0065_teacherfollowupregistersettings",
                    interactive=False, verbosity=0,
                )
                with connection.cursor() as cursor:
                    table_exists = table_name in connection.introspection.table_names(cursor)
            if not table_exists:
                raise RuntimeError(
                    "The teacher follow-up settings table is still missing after migration."
                )
            saved_settings = TeacherFollowupRegisterSettings.objects.filter(teacher=teacher).first()
        except Exception:
            settings_table_ready = False
            logger.exception("Unable to initialize/read teacher follow-up register settings")
            # Keep the register page usable; the persistence failure is logged,
            # and a warning is shown only if the user explicitly tries to save.
    saved_criteria = []
    if saved_settings:
        for item in saved_settings.criteria or []:
            if not isinstance(item, dict) or not str(item.get("name", "")).strip():
                continue
            try:
                weight = Decimal(str(item.get("weight", "0")))
            except (InvalidOperation, TypeError, ValueError):
                weight = Decimal("0")
            saved_criteria.append({"name": str(item["name"]).strip(), "weight": weight})

    if request.method == "POST":
        action = request.POST.get("action", "print")
        semester_values = request.POST.getlist("semesters")
        semesters = tuple(number for number in (1, 2) if str(number) in semester_values)

        if not teacher:
            messages.error(request, "اختر المعلم أولًا.")
            return redirect("followup_register")

        criteria, errors = _parse_followup_criteria(request.POST)
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, "school/followup_register.html", {
                "teachers": teachers,
                "selected_teacher": teacher,
                "available_classes": available_classes,
                "selected_class_ids": set(request.POST.getlist("class_ids")),
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
                "selected_semesters": set(semester_values),
            })

        # Persist criteria as soon as they validate, so printing and cover printing
        # both retain them even if the user later changes the selected classes.
        # Printing must remain available even if the optional persistence table
        # cannot be initialized. Saving settings is blocked explicitly, while a
        # print request continues using the criteria submitted with this form.
        if not settings_table_ready and action == "save":
            messages.error(request, "تعذر حفظ البنود لأن جدول الحفظ غير متاح حاليًا. يمكنك طباعة الدفتر بالبنود الظاهرة، ولم تتأثر بيانات الطلاب.")
            return redirect(
                f"/teachers/followup-register/?teacher={teacher.pk}"
                if role == "admin" else "followup_register"
            )

        if settings_table_ready:
          try:
            TeacherFollowupRegisterSettings.objects.update_or_create(
                teacher=teacher,
                defaults={
                    "criteria": [
                        {"name": item["name"], "weight": str(item["weight"])}
                        for item in criteria
                    ]
                },
            )
          except Exception:
            logger.exception("Unable to save teacher follow-up register settings")
            if action == "save":
                messages.error(request, "تعذر حفظ البنود في قاعدة البيانات. يمكنك طباعة الدفتر بالبنود الحالية؛ ولم تتأثر بيانات الطلاب.")
                return redirect(
                    f"/teachers/followup-register/?teacher={teacher.pk}"
                    if role == "admin" else "followup_register"
                )

        if action == "save":
            messages.success(request, f"تم حفظ بنود دفتر المتابعة للمعلم {teacher.full_name}، وستظهر عند العودة إلى هذه الصفحة.")
            return redirect(
                f"/teachers/followup-register/?teacher={teacher.pk}"
                if role == "admin" else "followup_register"
            )

        if not semesters:
            messages.error(request, "اختر الفصل الأول أو الفصل الثاني أو كليهما.")
            return render(request, "school/followup_register.html", {
                "teachers": teachers,
                "selected_teacher": teacher,
                "available_classes": available_classes,
                "selected_class_ids": set(request.POST.getlist("class_ids")),
                "criteria_form_rows": [
                    {"name": item["name"], "weight": item["weight"]}
                    for item in criteria
                ],
                "row_count": row_count,
                "row_options": range(MIN_REGISTER_STUDENTS, MAX_REGISTER_STUDENTS + 1),
                "start_year": start_year,
                "default_criteria": False,
                "selected_semesters": set(semester_values),
            })

        selected_ids = []
        for raw_id in request.POST.getlist("class_ids"):
            if raw_id.isdigit() and int(raw_id) not in selected_ids:
                selected_ids.append(int(raw_id))
        allowed_ids = set(available_classes.values_list("pk", flat=True))
        selected_ids = [class_id for class_id in selected_ids if class_id in allowed_ids]
        classes_by_id = {cls.pk: cls for cls in available_classes.filter(pk__in=selected_ids)}
        selected_classes = [classes_by_id[class_id] for class_id in selected_ids if class_id in classes_by_id]
        if not selected_classes:
            messages.error(request, "تم حفظ البنود، لكن حدد شعبة أو صفًا واحدًا على الأقل للطباعة.")
            return redirect(
                f"/teachers/followup-register/?teacher={teacher.pk}"
                if role == "admin" else "followup_register"
            )

        context = _followup_print_context(
            request, teacher, selected_classes, criteria, row_count, start_year,
            semesters=semesters,
        )
        context["print_cover_only"] = action == "cover"
        template = (
            "school/followup_register_cover.html"
            if action == "cover" else "school/followup_register_print.html"
        )
        return render(request, template, context)

    criteria_form_rows = (
        [{"name": item["name"], "weight": item["weight"]} for item in saved_criteria]
        if saved_criteria else [{"name": "", "weight": ""}]
    )
    return render(request, "school/followup_register.html", {
        "teachers": teachers,
        "selected_teacher": teacher,
        "available_classes": available_classes,
        "selected_class_ids": set(),
        "criteria_form_rows": criteria_form_rows,
        "row_count": row_count,
        "row_options": range(MIN_REGISTER_STUDENTS, MAX_REGISTER_STUDENTS + 1),
        "start_year": start_year,
        "default_criteria": not bool(saved_criteria),
    })
