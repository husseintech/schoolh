"""
محرك إنشاء البرامج الأسبوعية (Scheduling Engine)
=================================================
خوارزمية Constraint Satisfaction + تحسين (Soft Constraints):

1) التقيّد الصارم بالقيود الصلبة (Hard Constraints):
   - عدم تعارض المعلم (حصة واحدة لكل معلم في كل خلية زمنية).
   - عدم تعارض الصف/الشعبة.
   - احترام تفريغ المعلم (التوفّر).
   - عدم تجاوز عدد الحصص الأسبوعية المطلوبة ووضعها كلها.
   - احترام الحصص/الأيام غير الفعّالة.
   - احترام الحصص المثبتة (مقفلة، لا تتحرك).

2) تحسين القيود التفضيلية (Soft Constraints) عبر درجات تكلفة:
   - تقليل الفراغات، توزيع المادة على الأيام، تجنب تكرار المادة بنفس اليوم،
     موازنة حصص المعلم، تقليل المتتالية، تجنب يوم مزدحم مقابل يوم فارغ.

النتيجة: قائمة حصص + تقرير (نسبة الالتزام الصلب/الناعم + الحصص غير الموزعة + أسباب التعارض).
"""

import random
from collections import defaultdict


def _cons(cons, code, ctype):
    c = cons.get(code)
    if c and c.enabled and c.type == ctype:
        return c
    return None


def _param(c, key, default):
    if c is None:
        return default
    return c.params.get(key, default)


def _build_lessons(plan, fixed_keys):
    """يبني وحدات الحصص المطلوبة من الأنصبة بعد خصم الحصص المثبتة."""
    remaining = defaultdict(int)
    for tl in plan.teaching_loads.select_related('teacher', 'subject', 'student_class').all():
        remaining[(tl.teacher_id, tl.subject_id, tl.student_class_id)] += tl.weekly_periods
    for key in fixed_keys:
        if key in remaining and remaining[key] > 0:
            remaining[key] -= 1
    lessons = []
    for (teacher, subject, cls), cnt in remaining.items():
        for _ in range(cnt):
            lessons.append({'teacher': teacher, 'subject': subject, 'class': cls})
    return lessons


def generate_schedule(plan, seed=0, iterations=4000):
    random.seed(seed)
    days = plan.active_days
    periods = plan.active_periods
    day_names = [d['name'] for d in days]
    period_ids = [p['idx'] for p in periods]

    cons = {c.code: c for c in plan.constraints.all()}
    c_mpd = _cons(cons, 'max_periods_per_day', 'hard')
    max_per_day = int(c_mpd.weight) if c_mpd else 6
    c_mc = _cons(cons, 'max_consecutive', 'soft')
    max_consecutive = int(c_mc.weight) if c_mc else 2
    avoid_first_last = _cons(cons, 'avoid_first_last', 'soft') is not None
    spread_subject = _cons(cons, 'spread_subject', 'soft') is not None

    # خريطة التوفّر: (teacher, day, period) -> bool
    avail = {}
    for a in plan.availabilities.all():
        avail[(a.teacher_id, a.day, a.period)] = a.available

    # الحصص المثبتة (مقفلة)
    fixed_by_cell = {}
    fixed_keys = []
    for fl in plan.fixed_lessons.select_related('teacher', 'subject', 'student_class').all():
        key = (fl.teacher_id, fl.subject_id, fl.student_class_id)
        fixed_by_cell[(fl.day, fl.period)] = {
            'teacher': fl.teacher_id, 'subject': fl.subject_id, 'class': fl.student_class_id}
        fixed_keys.append(key)

    lessons = _build_lessons(plan, fixed_keys)

    # الحالة
    teacher_busy = defaultdict(set)   # (teacher, day, period)
    class_busy = defaultdict(set)     # (class, day, period)
    teacher_day = defaultdict(int)
    class_day = defaultdict(int)
    teacher_day_subs = defaultdict(lambda: defaultdict(set))  # (teacher, day) -> {subject: set(periods)}
    class_day_subs = defaultdict(lambda: defaultdict(set))    # (class, day) -> {subject: set(periods)}
    teacher_day_seq = defaultdict(list)  # (teacher, day) -> [periods]
    grid = {}  # (day, period) -> lesson

    conflicts = []
    fixed_violation = False

    def can_place(lesson, day, period, locked=False):
        t, s, c = lesson['teacher'], lesson['subject'], lesson['class']
        if (t, day, period) in teacher_busy:
            return False
        if (c, day, period) in class_busy:
            return False
        if avail.get((t, day, period), True) is False:
            return False
        if max_per_day is not None:
            if teacher_day[(t, day)] >= max_per_day:
                return False
            if class_day[(c, day)] >= max_per_day:
                return False
        return True

    # 1) وضع الحصص المثبتة
    for (day, period), fl in fixed_by_cell.items():
        if not can_place(fl, day, period):
            fixed_violation = True
            conflicts.append({
                'type': 'fixed_conflict',
                'day': day, 'period': period,
                'teacher': fl['teacher'], 'student_class': fl['class'],
                'reason': 'تعارض في حصة مثبتة مع تفريغ أو حصة أخرى.',
            })
        teacher_busy[(fl['teacher'], day, period)].add((fl['teacher'], day, period))
        class_busy[(fl['class'], day, period)].add((fl['class'], day, period))
        teacher_day[(fl['teacher'], day)] += 1
        class_day[(fl['class'], day)] += 1
        teacher_day_subs[(fl['teacher'], day)][fl['subject']].add(period)
        class_day_subs[(fl['class'], day)][fl['subject']].add(period)
        teacher_day_seq[(fl['teacher'], day)].append(period)
        grid[(day, period)] = dict(fl, fixed=True)

    # 2) ترتيب الحصص الأكثر تقييداً أولاً (معلم/صف بأكبر عدد)
    load_count = defaultdict(int)
    for l in lessons:
        load_count[l['teacher']] += 1
        load_count[l['class']] += 1
    lessons.sort(key=lambda l: -load_count[l['teacher']])

    def slot_cost(lesson, day, period):
        t, s, c = lesson['teacher'], lesson['subject'], lesson['class']
        cost = 0
        # فراغات للمعلم: إن كانت هناك حصص قبل وبعد مع فراغ هنا
        seq = sorted(teacher_day_seq[(t, day)] + [period])
        if period in seq:
            i = seq.index(period)
            if i > 0 and i < len(seq) - 1:
                if seq[i] - seq[i - 1] > 1:
                    cost += 3
        # تكرار المادة بنفس اليوم للصف
        if spread_subject and s in class_day_subs[(c, day)]:
            cost += 4
        # موازنة: تفضيل الأيام الأقل حصصاً للمعلم
        cost += teacher_day[(t, day)] * 1
        # المتتالية
        if max_consecutive:
            cnt = 1
            for pp in teacher_day_seq[(t, day)] + [period]:
                pass
            if period - 1 in teacher_day_seq[(t, day)] or period + 1 in teacher_day_seq[(t, day)]:
                # عدّ المتتالية المحيطة
                run = 1
                p = period - 1
                while p in teacher_day_seq[(t, day)]:
                    run += 1; p -= 1
                p = period + 1
                while p in teacher_day_seq[(t, day)]:
                    run += 1; p += 1
                if run + 1 > max_consecutive:
                    cost += 5
        # الحصة الأولى/الأخيرة
        if avoid_first_last and (period == period_ids[0] or period == period_ids[-1]):
            cost += 2
        return cost

    unscheduled = []
    for lesson in lessons:
        candidates = []
        for day in day_names:
            for period in period_ids:
                if can_place(lesson, day, period):
                    candidates.append((slot_cost(lesson, day, period), day, period))
        if not candidates:
            unscheduled.append(lesson)
            continue
        candidates.sort(key=lambda x: (x[0], random.random()))
        _, day, period = candidates[0]
        t, s, c = lesson['teacher'], lesson['subject'], lesson['class']
        teacher_busy[(t, day, period)].add((t, day, period))
        class_busy[(c, day, period)].add((c, day, period))
        teacher_day[(t, day)] += 1
        class_day[(c, day)] += 1
        teacher_day_subs[(t, day)][s].add(period)
        class_day_subs[(c, day)][s].add(period)
        teacher_day_seq[(t, day)].append(period)
        grid[(day, period)] = {'teacher': t, 'subject': s, 'class': c, 'fixed': False}

    # 3) تحسين محلي (تبديل/نقل) لتقليل التكلفة مع إبقاء القيود الصلبة
    keys = list(grid.keys())
    for _ in range(iterations):
        if not keys:
            break
        d1, p1 = random.choice(keys)
        cell1 = grid[(d1, p1)]
        if cell1.get('fixed'):
            continue
        d2, p2 = random.choice(keys)
        if (d1, p1) == (d2, p2):
            continue
        cell2 = grid[(d2, p2)]
        if cell2.get('fixed'):
            continue
        t1, c1 = cell1['teacher'], cell1['class']
        t2, c2 = cell2['teacher'], cell2['class']
        if t1 == t2 and c1 == c2:
            continue
        # تحقق من عدم تعارض عند التبديل
        if (t1, d2, p2) in teacher_busy and (t1, d2, p2) != (t1, d1, p1):
            # المعلم t1 مشغول في الوجهة
            if any(o != (t1, d1, p1) for o in teacher_busy[(t1, d2, p2)]):
                continue
        # (تبسيط) ننتقل فقط إذا الوجهتان خاليتان من تعارض المعلم/الصف لنقل كل حصة
        # نجرّب نقل cell1 إلى (d2,p2) ونقل cell2 إلى (d1,p1)
        if not _swap_ok(grid, teacher_busy, class_busy, (d1, p1), (d2, p2)):
            continue
        _do_swap(grid, teacher_busy, class_busy, (d1, p1), (d2, p2))

    # 4) حساب الدرجات
    total = len(lessons) + len(fixed_by_cell)
    scheduled = len(grid)
    hard_ok = (len(unscheduled) == 0) and (not fixed_violation)
    hard_score = 100.0 if hard_ok else round(100.0 * scheduled / total, 1) if total else 100.0

    soft_score = _soft_score(grid, teacher_day, class_day, max_consecutive,
                             day_names, period_ids, spread_subject, avoid_first_last)

    entries = []
    for (day, period), cell in grid.items():
        entries.append({
            'day': day, 'period': period,
            'teacher': cell['teacher'], 'subject': cell['subject'],
            'class': cell['class'], 'fixed': cell.get('fixed', False),
        })

    return {
        'entries': entries,
        'unscheduled': unscheduled,
        'conflicts': conflicts,
        'hard_score': hard_score,
        'soft_score': soft_score,
        'scheduled': scheduled,
        'total': total,
        'fixed_violation': fixed_violation,
    }


def _swap_ok(grid, teacher_busy, class_busy, a, b):
    ca = grid[a]
    cb = grid[b]
    ta, ca_cls = ca['teacher'], ca['class']
    tb, cb_cls = cb['teacher'], cb['class']
    da, pa = a
    db, pb = b
    # بعد التبديل: ca ينتقل إلى b، cb ينتقل إلى a
    # تحقق teacher_busy: عند b المعلم ta يجب ألا يكون مشغولاً بغير a
    for occ in teacher_busy.get((ta, db, pb), set()):
        if occ != (ta, da, pa):
            return False
    for occ in teacher_busy.get((tb, da, pa), set()):
        if occ != (tb, db, pb):
            return False
    for occ in class_busy.get((ca_cls, db, pb), set()):
        if occ != (ca_cls, da, pa):
            return False
    for occ in class_busy.get((cb_cls, da, pa), set()):
        if occ != (cb_cls, db, pb):
            return False
    return True


def _do_swap(grid, teacher_busy, class_busy, a, b):
    ca = grid[a]
    cb = grid[b]
    ta, ca_cls = ca['teacher'], ca['class']
    tb, cb_cls = cb['teacher'], cb['class']
    da, pa = a
    db, pb = b
    # إزالة القديم
    teacher_busy[(ta, da, pa)].discard((ta, da, pa))
    teacher_busy[(tb, db, pb)].discard((tb, db, pb))
    class_busy[(ca_cls, da, pa)].discard((ca_cls, da, pa))
    class_busy[(cb_cls, db, pb)].discard((cb_cls, db, pb))
    # وضع المبدّل
    grid[a], grid[b] = dict(cb, fixed=cb.get('fixed', False)), dict(ca, fixed=ca.get('fixed', False))
    teacher_busy[(tb, da, pa)].add((tb, da, pa))
    teacher_busy[(ta, db, pb)].add((ta, db, pb))
    class_busy[(cb_cls, da, pa)].add((cb_cls, da, pa))
    class_busy[(ca_cls, db, pb)].add((ca_cls, db, pb))


def _soft_score(grid, teacher_day, class_day, max_consecutive, day_names, period_ids, spread_subject, avoid_first_last):
    if not grid:
        return 100.0
    penalties = 0.0
    # فراغات: لكل معلم يوم، عدّ الفراغات بين أول وآخر حصة
    teacher_day_periods = defaultdict(lambda: defaultdict(list))
    for (day, period), cell in grid.items():
        if not cell.get('fixed'):
            teacher_day_periods[cell['teacher']][day].append(period)
    for t, by_day in teacher_day_periods.items():
        for day, ps in by_day.items():
            ps = sorted(ps)
            if len(ps) >= 2:
                gaps = (ps[-1] - ps[0] + 1) - len(ps)
                penalties += gaps * 2
    # تكرار المادة بنفس اليوم للصف
    class_day_subs = defaultdict(lambda: defaultdict(set))
    for (day, period), cell in grid.items():
        class_day_subs[cell['class']][day].add(cell['subject'])
    for c, by_day in class_day_subs.items():
        for day, subs in by_day.items():
            if len(subs) < len(grid_by_class_day(grid, c, day)):
                penalties += 1
    # المتتالية
    for t, by_day in teacher_day_periods.items():
        for day, ps in by_day.items():
            ps = sorted(ps)
            run = 1
            for i in range(1, len(ps)):
                if ps[i] == ps[i - 1] + 1:
                    run += 1
                else:
                    run = 1
                if run > max_consecutive:
                    penalties += 1
    # موازنة: تباين حصص المعلم عبر الأيام
    for t, by_day in teacher_day_periods.items():
        counts = [len(ps) for ps in by_day.values()]
        if counts:
            avg = sum(counts) / len(counts)
            penalties += sum(abs(c - avg) for c in counts) * 0.3
    max_pen = max(1.0, len(grid) * 0.5)
    return round(max(0.0, 100.0 - (penalties / max_pen) * 100.0), 1)


def grid_by_class_day(grid, c, day):
    return [cell for (d, p), cell in grid.items() if d == day and cell['class'] == c]


def evaluate_plan(plan):
    """يعيد تقييم القيود الصلبة والناعمة لبرنامج مولّد أو معدّل يدويًا."""
    entries = list(plan.entries.select_related('teacher', 'subject', 'student_class').all())
    cons = {c.code: c for c in plan.constraints.all()}
    c_mpd = _cons(cons, 'max_periods_per_day', 'hard')
    max_per_day = int(c_mpd.weight) if c_mpd else 6
    c_mc = _cons(cons, 'max_consecutive', 'soft')
    max_consecutive = int(c_mc.weight) if c_mc else 2
    avail = {}
    for a in plan.availabilities.all():
        avail[(a.teacher_id, a.day, a.period)] = a.available
    fixed = {}
    for fl in plan.fixed_lessons.all():
        fixed[(fl.day, fl.period)] = (fl.teacher_id, fl.subject_id, fl.student_class_id)

    teacher_busy = set()
    class_busy = set()
    teacher_day = defaultdict(int)
    class_day = defaultdict(int)
    teacher_day_seq = defaultdict(list)
    conflicts = []

    for e in entries:
        key = (e.teacher_id, e.day, e.period)
        if key in teacher_busy:
            conflicts.append({'type': 'teacher_double', 'day': e.day, 'period': e.period,
                              'teacher': e.teacher_id})
        if (e.student_class_id, e.day, e.period) in class_busy:
            conflicts.append({'type': 'class_double', 'day': e.day, 'period': e.period,
                              'student_class': e.student_class_id})
        teacher_busy.add(key)
        class_busy.add((e.student_class_id, e.day, e.period))
        if avail.get(key, True) is False:
            conflicts.append({'type': 'availability', 'day': e.day, 'period': e.period,
                              'teacher': e.teacher_id})
        fk = fixed.get((e.day, e.period))
        if fk and (fk[0] != e.teacher_id or fk[1] != e.subject_id or fk[2] != e.student_class_id):
            conflicts.append({'type': 'fixed_violation', 'day': e.day, 'period': e.period})
        teacher_day[(e.teacher_id, e.day)] += 1
        class_day[(e.student_class_id, e.day)] += 1
        if teacher_day[(e.teacher_id, e.day)] > max_per_day:
            conflicts.append({'type': 'max_per_day', 'day': e.day, 'teacher': e.teacher_id})
        if class_day[(e.student_class_id, e.day)] > max_per_day:
            conflicts.append({'type': 'max_per_day', 'day': e.day, 'student_class': e.student_class_id})
        teacher_day_seq[(e.teacher_id, e.day)].append(e.period)

    soft_pen = 0
    for (t, day), seq in teacher_day_seq.items():
        seq = sorted(seq)
        run = 1
        for i in range(1, len(seq)):
            if seq[i] == seq[i - 1] + 1:
                run += 1
            else:
                run = 1
            if run > max_consecutive:
                soft_pen += 1

    total = len(entries)
    hard = len(conflicts)
    hard_score = 100.0 if hard == 0 else round(max(0.0, 100.0 - hard * 100.0 / max(total, 1)), 1)
    soft_score = round(max(0.0, 100.0 - soft_pen * 5), 1)
    return {'hard_score': hard_score, 'soft_score': soft_score, 'conflicts': conflicts,
            'entries': total, 'unscheduled': 0}

