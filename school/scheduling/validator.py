from collections import defaultdict


def validate(plan):
    """يفحص الجدول الموجود في DB (ScheduleEntry) ويكشف خروق القيود الصلبة.

    يعيد dict: { 'valid': bool, 'violations': [نصوص], 'hard_violations': int,
                 'soft_score': float, 'fixed_violation': bool }
    """
    entries = plan.entries.all()
    violations = []

    by_teacher_cell = defaultdict(list)
    by_class_cell = defaultdict(list)
    by_tl = defaultdict(int)
    fixed_count = defaultdict(int)

    for e in entries:
        by_teacher_cell[(e.teacher_id, e.day, e.period)].append(e)
        by_class_cell[(e.student_class_id, e.day, e.period)].append(e)
        by_tl[(e.teacher_id, e.subject_id, e.student_class_id)] += 1

    # تداخل المعلم
    for (t, d, p), lst in by_teacher_cell.items():
        if len(lst) > 1:
            violations.append("تداخل معلم: المعلم %s له حصتان في %s حصة %s." % (t, d, p))
    # تداخل الصف
    for (c, d, p), lst in by_class_cell.items():
        if len(lst) > 1:
            violations.append("تداخل صف: الصف %s له حصتان في %s حصة %s." % (c, d, p))

    # النصاب الدقيق
    sem = (plan.semester or '').strip()
    for tl in plan.teaching_loads.select_related('teacher', 'subject', 'student_class').all():
        if sem and tl.semester and tl.semester != sem:
            continue
        got = by_tl.get((tl.teacher_id, tl.subject_id, tl.student_class_id), 0)
        if got != tl.weekly_periods:
            violations.append(
                "نصاب ناقص/زائد: %s/%s/%s مطلوب %d فعليًا %d."
                % (tl.teacher_id, tl.subject_id, tl.student_class_id, tl.weekly_periods, got)
            )

    # التفريغ
    avail_map = {(a.teacher_id, a.day, a.period): a.available for a in plan.availabilities.all()}
    for e in entries:
        av = avail_map.get((e.teacher_id, e.day, e.period))
        if av is False:
            violations.append("خرق توفّر: المعلم %s في خانة غير متاحة %s/%s." % (e.teacher_id, e.day, e.period))

    # الحصص المثبتة
    fixed_violation = False
    fl_map = defaultdict(list)
    for fl in plan.fixed_lessons.all():
        fl_map[(fl.teacher_id, fl.subject_id, fl.student_class_id)].append((fl.day, fl.period))
    placed = defaultdict(list)
    for e in entries:
        placed[(e.teacher_id, e.subject_id, e.student_class_id)].append((e.day, e.period))
    for key, cells in fl_map.items():
        actual = placed.get(key, [])
        for cell in cells:
            if cell not in actual:
                violations.append("حصة مثبتة نُقلت/لم تُوضع: %s في %s." % (key, cell))
                fixed_violation = True

    # خانات غير فعّالة
    active_days = {d['name'] for d in plan.active_days}
    active_periods = {p['idx'] for p in plan.active_periods}
    for e in entries:
        if e.day not in active_days or e.period not in active_periods:
            violations.append("خانة خارج الأيام/الحصص الفعّالة: %s/%s." % (e.day, e.period))

    return {
        'valid': len(violations) == 0,
        'violations': violations,
        'hard_violations': len(violations),
        'soft_score': 0.0,
        'fixed_violation': fixed_violation,
    }
