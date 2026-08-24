"""
ظ…ط­ط±ظƒ ط¥ظ†ط´ط§ط، ط§ظ„ط¨ط±ط§ظ…ط¬ ط§ظ„ط£ط³ط¨ظˆط¹ظٹط© (Scheduling Engine)
=================================================
ط®ظˆط§ط±ط²ظ…ظٹط© Constraint Satisfaction + طھط­ط³ظٹظ† (Soft Constraints):

1) ط§ظ„طھظ‚ظٹظ‘ط¯ ط§ظ„طµط§ط±ظ… ط¨ط§ظ„ظ‚ظٹظˆط¯ ط§ظ„طµظ„ط¨ط© (Hard Constraints):
   - ط¹ط¯ظ… طھط¹ط§ط±ط¶ ط§ظ„ظ…ط¹ظ„ظ… (ط­طµط© ظˆط§ط­ط¯ط© ظ„ظƒظ„ ظ…ط¹ظ„ظ… ظپظٹ ظƒظ„ ط®ظ„ظٹط© ط²ظ…ظ†ظٹط©).
   - ط¹ط¯ظ… طھط¹ط§ط±ط¶ ط§ظ„طµظپ/ط§ظ„ط´ط¹ط¨ط©.
   - ط§ط­طھط±ط§ظ… طھظپط±ظٹط؛ ط§ظ„ظ…ط¹ظ„ظ… (ط§ظ„طھظˆظپظ‘ط±).
   - ط¹ط¯ظ… طھط¬ط§ظˆط² ط¹ط¯ط¯ ط§ظ„ط­طµطµ ط§ظ„ط£ط³ط¨ظˆط¹ظٹط© ط§ظ„ظ…ط·ظ„ظˆط¨ط© ظˆظˆط¶ط¹ظ‡ط§ ظƒظ„ظ‡ط§.
   - ط§ط­طھط±ط§ظ… ط§ظ„ط­طµطµ/ط§ظ„ط£ظٹط§ظ… ط؛ظٹط± ط§ظ„ظپط¹ظ‘ط§ظ„ط©.
   - ط§ط­طھط±ط§ظ… ط§ظ„ط­طµطµ ط§ظ„ظ…ط«ط¨طھط© (ظ…ظ‚ظپظ„ط©طŒ ظ„ط§ طھطھط­ط±ظƒ).

2) طھط­ط³ظٹظ† ط§ظ„ظ‚ظٹظˆط¯ ط§ظ„طھظپط¶ظٹظ„ظٹط© (Soft Constraints) ط¹ط¨ط± ط¯ط±ط¬ط§طھ طھظƒظ„ظپط©:
   - طھظ‚ظ„ظٹظ„ ط§ظ„ظپط±ط§ط؛ط§طھطŒ طھظˆط²ظٹط¹ ط§ظ„ظ…ط§ط¯ط© ط¹ظ„ظ‰ ط§ظ„ط£ظٹط§ظ…طŒ طھط¬ظ†ط¨ طھظƒط±ط§ط± ط§ظ„ظ…ط§ط¯ط© ط¨ظ†ظپط³ ط§ظ„ظٹظˆظ…طŒ
     ظ…ظˆط§ط²ظ†ط© ط­طµطµ ط§ظ„ظ…ط¹ظ„ظ…طŒ طھظ‚ظ„ظٹظ„ ط§ظ„ظ…طھطھط§ظ„ظٹط©طŒ طھط¬ظ†ط¨ ظٹظˆظ… ظ…ط²ط¯ط­ظ… ظ…ظ‚ط§ط¨ظ„ ظٹظˆظ… ظپط§ط±ط؛.

ط§ظ„ظ†طھظٹط¬ط©: ظ‚ط§ط¦ظ…ط© ط­طµطµ + طھظ‚ط±ظٹط± (ظ†ط³ط¨ط© ط§ظ„ط§ظ„طھط²ط§ظ… ط§ظ„طµظ„ط¨/ط§ظ„ظ†ط§ط¹ظ… + ط§ظ„ط­طµطµ ط؛ظٹط± ط§ظ„ظ…ظˆط²ط¹ط© + ط£ط³ط¨ط§ط¨ ط§ظ„طھط¹ط§ط±ط¶).
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


def _max_gap_run(occupied, all_periods):
    """ط£ط·ظˆظ„ ط³ظ„ط³ظ„ط© ظپط±ط§ط؛ط§طھ ظ…طھطھط§ظ„ظٹط© ط¨ظٹظ† ط§ظ„ط­طµطµ ط§ظ„ظ…طھط§ط­ط©."""
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
    """ظٹط¨ظ†ظٹ ظˆط­ط¯ط§طھ ط§ظ„ط­طµطµ ط§ظ„ظ…ط·ظ„ظˆط¨ط© ظ…ظ† ط§ظ„ط£ظ†طµط¨ط© ط¨ط¹ط¯ ط®طµظ… ط§ظ„ط­طµطµ ط§ظ„ظ…ط«ط¨طھط©."""
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

    # ط®ط±ظٹط·ط© ط§ظ„طھظˆظپظ‘ط±: (teacher, day, period) -> bool
    avail = {}
    for a in plan.availabilities.all():
        avail[(a.teacher_id, a.day, a.period)] = a.available

    # ط§ظ„ط­طµطµ ط§ظ„ظ…ط«ط¨طھط© (ظ…ظ‚ظپظ„ط©)
    fixed_by_cell = {}
    fixed_keys = []
    for fl in plan.fixed_lessons.select_related('teacher', 'subject', 'student_class').all():
        key = (fl.teacher_id, fl.subject_id, fl.student_class_id)
        fixed_by_cell[(fl.day, fl.period)] = {
            'teacher': fl.teacher_id, 'subject': fl.subject_id, 'class': fl.student_class_id}
        fixed_keys.append(key)

    lessons = _build_lessons(plan, fixed_keys)

    # ط§ظ„ط­ط§ظ„ط©
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

    # 1) ظˆط¶ط¹ ط§ظ„ط­طµطµ ط§ظ„ظ…ط«ط¨طھط©
    for (day, period), fl in fixed_by_cell.items():
        if not can_place(fl, day, period):
            fixed_violation = True
            conflicts.append({
                'type': 'fixed_conflict',
                'day': day, 'period': period,
                'teacher': fl['teacher'], 'student_class': fl['class'],
                'reason': 'طھط¹ط§ط±ط¶ ظپظٹ ط­طµط© ظ…ط«ط¨طھط© ظ…ط¹ طھظپط±ظٹط؛ ط£ظˆ ط­طµط© ط£ط®ط±ظ‰.',
            })
        teacher_busy[(fl['teacher'], day, period)].add((fl['teacher'], day, period))
        class_busy[(fl['class'], day, period)].add((fl['class'], day, period))
        teacher_day[(fl['teacher'], day)] += 1
        class_day[(fl['class'], day)] += 1
        teacher_day_subs[(fl['teacher'], day)][fl['subject']].add(period)
        class_day_subs[(fl['class'], day)][fl['subject']].add(period)
        teacher_day_seq[(fl['teacher'], day)].append(period)
        lesson_day_count[(fl['teacher'], fl['subject'], fl['class'], day)] += 1
        teacher_period_days[(fl['teacher'], period)].add(day)
        teacher_day_periods[(fl['teacher'], day)].append(period)
        grid[(day, period)] = dict(fl, fixed=True)

    # 2) طھط±طھظٹط¨ ط§ظ„ط­طµطµ ط§ظ„ط£ظƒط«ط± طھظ‚ظٹظٹط¯ط§ظ‹ ط£ظˆظ„ط§ظ‹ (ظ…ط¹ظ„ظ…/طµظپ ط¨ط£ظƒط¨ط± ط¹ط¯ط¯)
    load_count = defaultdict(int)
    for l in lessons:
        load_count[l['teacher']] += 1
        load_count[l['class']] += 1
    lessons.sort(key=lambda l: -load_count[l['teacher']])

    def slot_cost(lesson, day, period):
        t, s, c = lesson['teacher'], lesson['subject'], lesson['class']
        cost = 0
        # ظپط±ط§ط؛ط§طھ ظ„ظ„ظ…ط¹ظ„ظ…: ط¥ظ† ظƒط§ظ†طھ ظ‡ظ†ط§ظƒ ط­طµطµ ظ‚ط¨ظ„ ظˆط¨ط¹ط¯ ظ…ط¹ ظپط±ط§ط؛ ظ‡ظ†ط§
        seq = sorted(teacher_day_seq[(t, day)] + [period])
        if period in seq:
            i = seq.index(period)
            if i > 0 and i < len(seq) - 1:
                if seq[i] - seq[i - 1] > 1:
                    cost += 3
        # طھظƒط±ط§ط± ط§ظ„ظ…ط§ط¯ط© ط¨ظ†ظپط³ ط§ظ„ظٹظˆظ… ظ„ظ„ظ…ط¹ظ„ظ…
        if spread_max is not None and len(teacher_day_subs[(t, day)][s]) >= spread_max:
            cost += 4
        # ظ…ظˆط§ط²ظ†ط©: طھظپط¶ظٹظ„ ط§ظ„ط£ظٹط§ظ… ط§ظ„ط£ظ‚ظ„ ط­طµطµط§ظ‹ ظ„ظ„ظ…ط¹ظ„ظ…
        cost += teacher_day[(t, day)] * 1
        # ط§ظ„ظ…طھطھط§ظ„ظٹط©
        if max_consecutive:
            cnt = 1
            for pp in teacher_day_seq[(t, day)] + [period]:
                pass
            if period - 1 in teacher_day_seq[(t, day)] or period + 1 in teacher_day_seq[(t, day)]:
                # ط¹ط¯ظ‘ ط§ظ„ظ…طھطھط§ظ„ظٹط© ط§ظ„ظ…ط­ظٹط·ط©
                run = 1
                p = period - 1
                while p in teacher_day_seq[(t, day)]:
                    run += 1; p -= 1
                p = period + 1
                while p in teacher_day_seq[(t, day)]:
                    run += 1; p += 1
                if run + 1 > max_consecutive:
                    cost += 5
        # ط§ظ„ط­طµط© ط§ظ„ط£ظˆظ„ظ‰/ط§ظ„ط£ط®ظٹط±ط©
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

    # 3) طھط­ط³ظٹظ† ظ…ط­ظ„ظٹ (طھط¨ط¯ظٹظ„/ظ†ظ‚ظ„) ظ„طھظ‚ظ„ظٹظ„ ط§ظ„طھظƒظ„ظپط© ظ…ط¹ ط¥ط¨ظ‚ط§ط، ط§ظ„ظ‚ظٹظˆط¯ ط§ظ„طµظ„ط¨ط©
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
        # طھط­ظ‚ظ‚ ظ…ظ† ط¹ط¯ظ… طھط¹ط§ط±ط¶ ط¹ظ†ط¯ ط§ظ„طھط¨ط¯ظٹظ„
        if (t1, d2, p2) in teacher_busy and (t1, d2, p2) != (t1, d1, p1):
            # ط§ظ„ظ…ط¹ظ„ظ… t1 ظ…ط´ط؛ظˆظ„ ظپظٹ ط§ظ„ظˆط¬ظ‡ط©
            if any(o != (t1, d1, p1) for o in teacher_busy[(t1, d2, p2)]):
                continue
        # (طھط¨ط³ظٹط·) ظ†ظ†طھظ‚ظ„ ظپظ‚ط· ط¥ط°ط§ ط§ظ„ظˆط¬ظ‡طھط§ظ† ط®ط§ظ„ظٹطھط§ظ† ظ…ظ† طھط¹ط§ط±ط¶ ط§ظ„ظ…ط¹ظ„ظ…/ط§ظ„طµظپ ظ„ظ†ظ‚ظ„ ظƒظ„ ط­طµط©
        # ظ†ط¬ط±ظ‘ط¨ ظ†ظ‚ظ„ cell1 ط¥ظ„ظ‰ (d2,p2) ظˆظ†ظ‚ظ„ cell2 ط¥ظ„ظ‰ (d1,p1)
        if not _swap_ok(grid, teacher_busy, class_busy, (d1, p1), (d2, p2)):
            continue
        _do_swap(grid, teacher_busy, class_busy, (d1, p1), (d2, p2))

    # 4) ط­ط³ط§ط¨ ط§ظ„ط¯ط±ط¬ط§طھ
    total = len(lessons) + len(fixed_by_cell)
    scheduled = len(grid)
    hard_ok = (len(unscheduled) == 0) and (not fixed_violation)
    hard_score = 100.0 if hard_ok else round(100.0 * scheduled / total, 1) if total else 100.0

    soft_score = _soft_score(grid, teacher_day, class_day, max_consecutive,
                             day_names, period_ids, spread_max is not None, avoid_first_last)

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
    # ط¨ط¹ط¯ ط§ظ„طھط¨ط¯ظٹظ„: ca ظٹظ†طھظ‚ظ„ ط¥ظ„ظ‰ bطŒ cb ظٹظ†طھظ‚ظ„ ط¥ظ„ظ‰ a
    # طھط­ظ‚ظ‚ teacher_busy: ط¹ظ†ط¯ b ط§ظ„ظ…ط¹ظ„ظ… ta ظٹط¬ط¨ ط£ظ„ط§ ظٹظƒظˆظ† ظ…ط´ط؛ظˆظ„ط§ظ‹ ط¨ط؛ظٹط± a
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
    # ط¥ط²ط§ظ„ط© ط§ظ„ظ‚ط¯ظٹظ…
    teacher_busy[(ta, da, pa)].discard((ta, da, pa))
    teacher_busy[(tb, db, pb)].discard((tb, db, pb))
    class_busy[(ca_cls, da, pa)].discard((ca_cls, da, pa))
    class_busy[(cb_cls, db, pb)].discard((cb_cls, db, pb))
    # ظˆط¶ط¹ ط§ظ„ظ…ط¨ط¯ظ‘ظ„
    grid[a], grid[b] = dict(cb, fixed=cb.get('fixed', False)), dict(ca, fixed=ca.get('fixed', False))
    teacher_busy[(tb, da, pa)].add((tb, da, pa))
    teacher_busy[(ta, db, pb)].add((ta, db, pb))
    class_busy[(cb_cls, da, pa)].add((cb_cls, da, pa))
    class_busy[(ca_cls, db, pb)].add((ca_cls, db, pb))


def _soft_score(grid, teacher_day, class_day, max_consecutive, day_names, period_ids, spread_subject, avoid_first_last):
    if not grid:
        return 100.0
    penalties = 0.0
    # ظپط±ط§ط؛ط§طھ: ظ„ظƒظ„ ظ…ط¹ظ„ظ… ظٹظˆظ…طŒ ط¹ط¯ظ‘ ط§ظ„ظپط±ط§ط؛ط§طھ ط¨ظٹظ† ط£ظˆظ„ ظˆط¢ط®ط± ط­طµط©
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
    # طھظƒط±ط§ط± ط§ظ„ظ…ط§ط¯ط© ط¨ظ†ظپط³ ط§ظ„ظٹظˆظ… ظ„ظ„طµظپ
    class_day_subs = defaultdict(lambda: defaultdict(set))
    for (day, period), cell in grid.items():
        class_day_subs[cell['class']][day].add(cell['subject'])
    for c, by_day in class_day_subs.items():
        for day, subs in by_day.items():
            if len(subs) < len(grid_by_class_day(grid, c, day)):
                penalties += 1
    # ط§ظ„ظ…طھطھط§ظ„ظٹط©
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
    # ظ…ظˆط§ط²ظ†ط©: طھط¨ط§ظٹظ† ط­طµطµ ط§ظ„ظ…ط¹ظ„ظ… ط¹ط¨ط± ط§ظ„ط£ظٹط§ظ…
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
    """ظٹط¹ظٹط¯ طھظ‚ظٹظٹظ… ط§ظ„ظ‚ظٹظˆط¯ ط§ظ„طµظ„ط¨ط© ظˆط§ظ„ظ†ط§ط¹ظ…ط© ظ„ط¨ط±ظ†ط§ظ…ط¬ ظ…ظˆظ„ظ‘ط¯ ط£ظˆ ظ…ط¹ط¯ظ‘ظ„ ظٹط¯ظˆظٹظ‹ط§."""
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

