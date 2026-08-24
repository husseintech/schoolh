from collections import defaultdict


def pre_validate(plan, lessons, day_names, period_ids):
    """فحص مسبق سريع قبل تشغيل Solver. يعيد قائمة أسباب (عربية) أو [] إن سليم."""
    diags = []
    n_days = len(day_names)
    n_periods = len(period_ids)
    capacity = n_days * n_periods

    # سعة الصف
    by_class = defaultdict(int)
    for l in lessons:
        by_class[l['class']] += l['required']
    for c, total in by_class.items():
        if total > capacity:
            diags.append(
                "الصف رقم %s يحتاج %d حصة أسبوعيًا لكن السعة القصوى = الأيام × الحصص/اليوم = %d × %d = %d ⇒ مستحيل."
                % (c, total, n_days, n_periods, capacity)
            )

    # توفّر المعلم
    avail = defaultdict(list)  # (teacher, day, period) -> available
    for a in plan.availabilities.all():
        avail[(a.teacher_id, a.day, a.period)].append(a.available)
    by_teacher = defaultdict(int)
    for l in lessons:
        by_teacher[l['teacher']] += l['required']
    for t, total in by_teacher.items():
        free = 0
        for d in day_names:
            for p in period_ids:
                vals = avail.get((t, d, p))
                if vals is None or all(vals):  # متاح افتراضيًا
                    free += 1
        if total > free:
            diags.append(
                "المعلم رقم %s مطلوب منه %d حصة أسبوعيًا لكن الفترات المتاحة له (بعد التفريغ) = %d فقط ⇒ مستحيل."
                % (t, total, free)
            )

    # تعارض الحصص المثبتة مع التوفّر
    for fl in plan.fixed_lessons.all():
        vals = avail.get((fl.teacher_id, fl.day, fl.period))
        if vals is not None and not all(vals):
            diags.append(
                "حصة مثبتة للمعلم %s يوم %s حصة %s، وهو غير متاح فيها ⇒ تعارض FixedLesson ↔ Availability."
                % (fl.teacher_id, fl.day, fl.period)
            )

    # تعارض حصة مثبتة مع سعة الصف/تكرار المعلم (نفس الخانة لمعلمين أو صفين)
    fixed_by_cell = defaultdict(list)
    for fl in plan.fixed_lessons.all():
        fixed_by_cell[(fl.day, fl.period)].append((fl.teacher_id, fl.student_class_id))
    for (d, p), lst in fixed_by_cell.items():
        teachers = [x[0] for x in lst]
        classes = [x[1] for x in lst]
        if len(teachers) != len(set(teachers)):
            diags.append("حصص مثبتة متعارضة: معلم واحد موزّع في نفس الخانة (%s, %s)." % (d, p))
        if len(classes) != len(set(classes)):
            diags.append("حصص مثبتة متعارضة: صف واحد موزّع في نفس الخانة (%s, %s)." % (d, p))

    return diags
