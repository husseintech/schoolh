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


def _max_gap_run(occupied, all_periods):
    """أطول سلسلة فراغات متتالية بين الحصص المتاحة."""
    occ = set(occupied)
    maxrun = cur = 0
    for p in all_periods:
        if p in occ:
            cur = 0
        else:
            cur += 1
            maxrun = max(maxrun, cur)
    return maxrun


def _build_lessons(plan, fixed_keys):
    """يبني وحدات الحصص المطلوبة من الأنصبة بعد خصم الحصص المثبّتة."""
    sem = (plan.semester or '').strip()
    remaining = defaultdict(int)
    for tl in plan.teaching_loads.select_related('teacher', 'subject', 'student_class').all():
        if sem and tl.semester and tl.semester != sem:
            continue
        remaining[(tl.teacher_id, tl.subject_id, tl.student_class_id)] += tl.weekly_periods
    for key in fixed_keys:
        if key in remaining and remaining[key] > 0:
            remaining[key] -= 1
    lessons = []
    for (teacher, subject, cls), cnt in remaining.items():
        for _ in range(cnt):
            lessons.append({'teacher': teacher, 'subject': subject, 'class': cls})
    return lessons


def generate_schedule(plan, seed=0, iterations=3000, restarts=12):
    """يولّد الجدول عبر عدّة محاولات عشوائية ويُبقي الأفضل (أسلوب مشابه لـ aSCTimetable)."""
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
    spread_c = _cons(cons, 'spread_subject', 'soft')
    spread_max = int(spread_c.params.get('max_per_day', 1)) if spread_c else None
    gap_c = _cons(cons, 'max_consecutive_gap', 'soft')
    max_gap = int(gap_c.params.get('max_gap', 1)) if gap_c else None
    period_repeat = []
    for c in plan.constraints.filter(code='period_repeat', enabled=True):
        try:
            period_repeat.append((int(c.params.get('period')), int(c.params.get('max_days', 1))))
        except (TypeError, ValueError):
            pass

    avail = {}
    for a in plan.availabilities.all():
        avail[(a.teacher_id, a.day, a.period)] = a.available

    fixed_by_cell = {}
    fixed_keys = []
    for fl in plan.fixed_lessons.select_related('teacher', 'subject', 'student_class').all():
        key = (fl.teacher_id, fl.subject_id, fl.student_class_id)
        fixed_by_cell[(fl.day, fl.period)] = {
            'teacher': fl.teacher_id, 'subject': fl.subject_id, 'class': fl.student_class_id}
        fixed_keys.append(key)

    lessons = _build_lessons(plan, fixed_keys)

    best = None
    for r in range(restarts):
        res = _attempt(plan, seed + r * 7919, iterations, days, day_names, period_ids,
                       max_per_day, max_consecutive, avoid_first_last, spread_max,
                       max_gap, period_repeat, avail, fixed_by_cell, lessons)
        if best is None:
            best = res
        else:
            key_new = (len(res['unscheduled']), -res['hard_score'], -res['soft_score'])
            key_best = (len(best['unscheduled']), -best['hard_score'], -best['soft_score'])
            if key_new < key_best:
                best = res
    return best


def _attempt(plan, seed, iterations, days, day_names, period_ids, max_per_day,
             max_consecutive, avoid_first_last, spread_max, max_gap, period_repeat,
             avail, fixed_by_cell, lessons):
    random.seed(seed)
    teacher_busy = defaultdict(set)   # (teacher, day, period)
    class_busy = defaultdict(set)     # (class, day, period)
    teacher_day = defaultdict(int)
    class_day = defaultdict(int)
    teacher_day_subs = defaultdict(lambda: defaultdict(set))  # (teacher, day) -> {subject: set(periods)}
    class_day_subs = defaultdict(lambda: defaultdict(set))    # (class, day) -> {subject: set(periods)}
    teacher_day_seq = defaultdict(list)  # (teacher, day) -> [periods]
    lesson_day_count = defaultdict(int)            # ((teacher, subject, class, day)) -> count
    teacher_period_days = defaultdict(set)  # (teacher, period) -> set(days)
    teacher_day_periods = defaultdict(list)  # (teacher, day) -> [periods]
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
        if spread_max is not None:
            if lesson_day_count[(t, s, c, day)] >= spread_max:
                return False
        if max_gap is not None:
            occ = teacher_day_periods[(t, day)] + [period]
            if _max_gap_run(occ, period_ids) > max_gap:
                return False
        if period_repeat:
            for (pr_period, pr_max) in period_repeat:
                if period == pr_period:
                    days_set = teacher_period_days[(t, period)]
                    if day not in days_set and len(days_set) >= pr_max:
                        return False
        return True

    # 1) وضع الحصص المثبّتة
    for (day, period), fl in fixed_by_cell.items():
        t, s, c = fl['teacher'], fl['subject'], fl['class']
        if (t, day, period) in teacher_busy or (c, day, period) in class_busy:
            fixed_violation = True
        if avail.get((t, day, period), True) is False:
            fixed_violation = True
        teacher_busy[(t, day, period)].add((t, day, period))
        class_busy[(c, day, period)].add((c, day, period))
        teacher_day[(t, day)] += 1
        class_day[(c, day)] += 1
        teacher_day_subs[(t, day)][s].add(period)
        class_day_subs[(c, day)][s].add(period)
        teacher_day_seq[(t, day)].append(period)
        lesson_day_count[(t, s, c, day)] += 1
        teacher_period_days[(t, period)].add(day)
        teacher_day_periods[(t, day)].append(period)
        grid[(day, period)] = dict(fl, fixed=True)

    # 2) ترتيب الحصص الأكثر تقييدًا أولًا
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
        # تكرار المادة بنفس اليوم للمعلم
        if spread_max is not None and len(teacher_day_subs[(t, day)][s]) >= spread_max:
            cost += 4
        # موازنة: تفضيل الأيام الأقل حصصًا للمعلم
        cost += teacher_day[(t, day)] * 1
        # المتتالية
        if max_consecutive:
            if period - 1 in teacher_day_seq[(t, day)] or period + 1 in teacher_day_seq[(t, day)]:
                run = 1
                p = period - 1
                while p in teacher_day_seq[(t, day)]:
                    run += 1; p -= 1
                p = period + 1
                while p in teacher_day_seq[(t, day)]:
                    run += 1; p += 1
                if run + 1 > max_consecutive:
                    cost += 5
        # أقصى فراغ متتالٍ للمعلم
        if max_gap is not None:
            occ = sorted(teacher_day_periods[(t, day)] + [period])
            excess = _max_gap_run(occ, period_ids) - max_gap
            if excess > 0:
                cost += 6 * excess
        # تكرار حصة معيّنة للمعلم بحد أيام
        if period_repeat:
            for (pr_period, pr_max) in period_repeat:
                if period == pr_period:
                    days_set = teacher_period_days[(t, period)]
                    if day not in days_set and len(days_set) >= pr_max:
                        cost += 6
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
        lesson_day_count[(t, s, c, day)] += 1
        teacher_period_days[(t, period)].add(day)
        teacher_day_periods[(t, day)].append(period)
        grid[(day, period)] = {'teacher': t, 'subject': s, 'class': c, 'fixed': False}

    # 3) تحسين محلّي (صعود تلّي) يقلّل العقوبة الكلية لقيود المعلمين
    keys = list(grid.keys())
    base_pen = _grid_penalty(grid, max_gap, period_repeat, period_ids, spread_max, max_consecutive, avoid_first_last)
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
        if not _swap_ok(grid, teacher_busy, class_busy, (d1, p1), (d2, p2)):
            continue
        _do_swap(grid, teacher_busy, class_busy, (d1, p1), (d2, p2))
        new_pen = _grid_penalty(grid, max_gap, period_repeat, period_ids, spread_max, max_consecutive, avoid_first_last)
        if new_pen <= base_pen or random.random() < 0.03:
            base_pen = new_pen
        else:
            _do_swap(grid, teacher_busy, class_busy, (d1, p1), (d2, p2))

    # 4) حساب الدرجات
    total = len(lessons) + len(fixed_by_cell)
    scheduled = len(grid)
    hard_ok = (len(unscheduled) == 0) and (not fixed_violation)
    hard_score = 100.0 if hard_ok else round(100.0 * scheduled / total, 1) if total else 100.0

    soft_score = _soft_score(grid, teacher_day, class_day, max_consecutive,
                             day_names, period_ids, spread_max is not None,
                             avoid_first_last, max_gap, period_repeat)

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
    teacher_busy[(ta, da, pa)].discard((ta, da, pa))
    teacher_busy[(tb, db, pb)].discard((tb, db, pb))
    class_busy[(ca_cls, da, pa)].discard((ca_cls, da, pa))
    class_busy[(cb_cls, db, pb)].discard((cb_cls, db, pb))
    grid[a], grid[b] = dict(cb, fixed=cb.get('fixed', False)), dict(ca, fixed=ca.get('fixed', False))
    teacher_busy[(tb, da, pa)].add((tb, da, pa))
    teacher_busy[(ta, db, pb)].add((ta, db, pb))
    class_busy[(cb_cls, da, pa)].add((cb_cls, da, pa))
    class_busy[(ca_cls, db, pb)].add((ca_cls, db, pb))


def _soft_score(grid, teacher_day, class_day, max_consecutive, day_names, period_ids,
                spread_subject, avoid_first_last, max_gap=None, period_repeat=None):
    if period_repeat is None:
        period_repeat = []
    if not grid:
        return 100.0
    penalties = 0.0
    teacher_day_periods = defaultdict(lambda: defaultdict(list))
    teacher_day_subs = defaultdict(lambda: defaultdict(set))
    for (day, period), cell in grid.items():
        if not cell.get('fixed'):
            teacher_day_periods[cell['teacher']][day].append(period)
            teacher_day_subs[cell['teacher']][day].add(cell['subject'])
    for t, by_day in teacher_day_periods.items():
        for day, ps in by_day.items():
            ps = sorted(ps)
            if len(ps) >= 2:
                gaps = (ps[-1] - ps[0] + 1) - len(ps)
                penalties += gaps * 2
            run = 1
            for i in range(1, len(ps)):
                if ps[i] == ps[i - 1] + 1:
                    run += 1
                else:
                    run = 1
                if run > max_consecutive:
                    penalties += 1
            if max_gap is not None:
                excess = _max_gap_run(ps, period_ids) - max_gap
                if excess > 0:
                    penalties += 3 * excess
            if avoid_first_last and (ps[0] == period_ids[0] or ps[-1] == period_ids[-1]):
                penalties += 1
    class_day_subs = defaultdict(lambda: defaultdict(set))
    for (day, period), cell in grid.items():
        class_day_subs[cell['class']][day].add(cell['subject'])
    for c, by_day in class_day_subs.items():
        for day, subs in by_day.items():
            if len(subs) < len(grid_by_class_day(grid, c, day)):
                penalties += 1
    teacher_period_days = defaultdict(lambda: defaultdict(set))
    for (day, period), cell in grid.items():
        if not cell.get('fixed'):
            teacher_period_days[cell['teacher']][period].add(day)
    for t, by_p in teacher_period_days.items():
        for period, days in by_p.items():
            for (pr_period, pr_max) in period_repeat:
                if period == pr_period and len(days) > pr_max:
                    penalties += 2 * (len(days) - pr_max)
    for t, by_day in teacher_day_periods.items():
        counts = [len(ps) for ps in by_day.values()]
        if counts:
            avg = sum(counts) / len(counts)
            penalties += sum(abs(c - avg) for c in counts) * 0.3
    max_pen = max(1.0, len(grid) * 0.5)
    return round(max(0.0, 100.0 - (penalties / max_pen) * 100.0), 1)


def _grid_penalty(grid, max_gap, period_repeat, period_ids, spread_max, max_consecutive, avoid_first_last):
    """عقوبة كلية لقيود المعلمين (تُقلّل أثناء البحث المحلّي)."""
    tdp = defaultdict(lambda: defaultdict(list))   # teacher -> day -> [periods]
    tpd = defaultdict(lambda: defaultdict(set))    # teacher -> period -> {days}
    tds = defaultdict(lambda: defaultdict(set))    # teacher -> day -> {subjects}
    for (day, period), cell in grid.items():
        if cell.get('fixed'):
            continue
        t = cell['teacher']; s = cell['subject']
        tdp[t][day].append(period)
        tpd[t][period].add(day)
        tds[t][day].add(s)
    pen = 0.0
    for t, by_day in tdp.items():
        for day, ps in by_day.items():
            ps = sorted(ps)
            if len(ps) >= 2:
                pen += ((ps[-1] - ps[0] + 1) - len(ps)) * 2
            mc = max_consecutive or 99
            run = 1
            for i in range(1, len(ps)):
                if ps[i] == ps[i - 1] + 1:
                    run += 1
                else:
                    run = 1
                if run > mc:
                    pen += 1
            if avoid_first_last and (ps[0] == period_ids[0] or ps[-1] == period_ids[-1]):
                pen += 1
            if max_gap is not None:
                excess = _max_gap_run(ps, period_ids) - max_gap
                if excess > 0:
                    pen += 3 * excess
            if spread_max is not None and len(tds[t][day]) > spread_max:
                pen += 2 * (len(tds[t][day]) - spread_max)
    for t, by_p in tpd.items():
        for period, days in by_p.items():
            for (pr_period, pr_max) in period_repeat:
                if period == pr_period and len(days) > pr_max:
                    pen += 2 * (len(days) - pr_max)
    return pen


def grid_by_class_day(grid, c, day):
    return [cell for (d, p), cell in grid.items() if d == day and cell['class'] == c]


def evaluate_plan(plan):
    """يعيد تقييم القيود الصلبة والناعمة لبرنامج مولّد أو معدّل يدويًا."""
    entries = list(plan.entries.select_related('teacher', 'subject', 'student_class').all())
    cons = {c.code: c for c in plan.constraints.all()}
    period_ids = [p['idx'] for p in plan.active_periods]
    c_mpd = _cons(cons, 'max_periods_per_day', 'hard')
    max_per_day = int(c_mpd.weight) if c_mpd else 6
    c_mc = _cons(cons, 'max_consecutive', 'soft')
    max_consecutive = int(c_mc.weight) if c_mc else 2
    spread_c = _cons(cons, 'spread_subject', 'soft')
    spread_max = int(spread_c.params.get('max_per_day', 1)) if spread_c else None
    gap_c = _cons(cons, 'max_consecutive_gap', 'soft')
    max_gap = int(gap_c.params.get('max_gap', 1)) if gap_c else None
    period_repeat = []
    for c in plan.constraints.filter(code='period_repeat', enabled=True):
        try:
            period_repeat.append((int(c.params.get('period')), int(c.params.get('max_days', 1))))
        except (TypeError, ValueError):
            pass
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
    lesson_day_count = defaultdict(int)
    teacher_period_days = defaultdict(set)
    teacher_day_periods = defaultdict(list)
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
        lesson_day_count[(e.teacher_id, e.subject_id, e.student_class_id, e.day)] += 1
        teacher_period_days[(e.teacher_id, e.period)].add(e.day)
        teacher_day_periods[(e.teacher_id, e.day)].append(e.period)

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

    if spread_max is not None:
        for (t, s, c, day), cnt in lesson_day_count.items():
            if cnt > spread_max:
                conflicts.append({'type': 'spread', 'day': day, 'teacher': t, 'subject': s})
    if max_gap is not None:
        for (t, day), ps in teacher_day_periods.items():
            if _max_gap_run(ps, period_ids) > max_gap:
                conflicts.append({'type': 'gap', 'day': day, 'teacher': t})
    for (pr_period, pr_max) in period_repeat:
        for (t, period), days_set in teacher_period_days.items():
            if period == pr_period and len(days_set) > pr_max:
                conflicts.append({'type': 'period_repeat', 'period': period, 'teacher': t})

    total = len(entries)
    hard = len(conflicts)
    hard_score = 100.0 if hard == 0 else round(max(0.0, 100.0 - hard * 100.0 / max(total, 1)), 1)
    soft_score = round(max(0.0, 100.0 - soft_pen * 5), 1)
    return {'hard_score': hard_score, 'soft_score': soft_score, 'conflicts': conflicts,
            'entries': total, 'unscheduled': 0}
