import random
from collections import defaultdict


def _cons(cons, code, ctype):
    c = cons.get(code)
    if c and c.enabled and c.type == ctype:
        return c
    return None


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


def _build_lessons(plan, fixed_by_cell):
    """يبني وحدات الحصص المطلوبة من الأنصبة بعد خصم الحصص المثبّتة.

    fixed_by_cell مفاتيحه (class, day, period).
    """
    sem = (plan.semester or '').strip()
    remaining = defaultdict(int)
    for tl in plan.teaching_loads.select_related('teacher', 'subject', 'student_class').all():
        if sem and tl.semester and tl.semester != sem:
            continue
        remaining[(tl.teacher_id, tl.subject_id, tl.student_class_id)] += tl.weekly_periods
    for (cls, day, period), fl in fixed_by_cell.items():
        key = (fl['teacher'], fl['subject'], cls)
        if remaining.get(key):
            remaining[key] -= 1
    lessons = []
    for (teacher, subject, cls), cnt in remaining.items():
        for _ in range(cnt):
            lessons.append({'teacher': teacher, 'subject': subject, 'class': cls})
    return lessons


def _prepare_constraints(plan):
    """يحمّل القيود المفعّلة مع مجموعات المعلمين/الصفوف المستهدفة."""
    cons = list(plan.constraints.filter(enabled=True).prefetch_related('teachers', 'classes'))
    groups = defaultdict(list)
    for c in cons:
        c._tids = set(c.teachers.values_list('id', flat=True))
        c._cids = set(c.classes.values_list('id', flat=True))
        groups[c.code].append(c)
    return groups


def _eff(groups, t, c):
    """القيم الفعّالة لقيد (معلم t، صف c) مع مراعاة النطاق."""
    max_per_day = None
    max_consecutive = None
    spread_max = None
    max_gap = None
    period_repeat = []
    avoid_first_last = False

    def applies(con):
        if con.scope == 'teachers':
            return t in con._tids
        if con.scope == 'classes':
            return c in con._cids
        return True

    for con in groups.get('max_periods_per_day', []):
        if applies(con):
            v = int(con.weight)
            max_per_day = v if max_per_day is None else min(max_per_day, v)
    for con in groups.get('max_consecutive', []):
        if applies(con):
            v = int(con.weight)
            max_consecutive = v if max_consecutive is None else min(max_consecutive, v)
    for con in groups.get('spread_subject', []):
        if applies(con):
            v = int((con.params or {}).get('max_per_day', 1))
            spread_max = v if spread_max is None else min(spread_max, v)
    for con in groups.get('max_consecutive_gap', []):
        if applies(con):
            v = int((con.params or {}).get('max_gap', 1))
            max_gap = v if max_gap is None else min(max_gap, v)
    for con in groups.get('period_repeat', []):
        if applies(con):
            p = (con.params or {}).get('period')
            m = (con.params or {}).get('max_days', 1)
            if p is not None:
                period_repeat.append((int(p), int(m)))
    for con in groups.get('avoid_first_last', []):
        if applies(con):
            avoid_first_last = True
    if max_consecutive is None:
        max_consecutive = 2
    if max_per_day is None:
        max_per_day = 6
    return {'max_per_day': max_per_day, 'max_consecutive': max_consecutive,
            'spread_max': spread_max, 'max_gap': max_gap,
            'period_repeat': period_repeat, 'avoid_first_last': avoid_first_last}


def generate_schedule(plan, seed=0, iterations=3000, restarts=12):
    """يولّد الجدول عبر عدّة محاولات عشوائية ويُبقي الأفضل (أسلوب مشابه لـ aSCTimetable).

    النموذج: كل صف له شبكته الخاصة (موازٍ لصفوف أخرى)، ويمنع أن يدرّس المعلم
    صفّين في آن واحد عبر teacher_busy.
    """
    days = plan.active_days
    periods = plan.active_periods
    day_names = [d['name'] for d in days]
    period_ids = [p['idx'] for p in periods]

    groups = _prepare_constraints(plan)
    eff_cache = {}

    def eff(t, c):
        k = (t, c)
        if k not in eff_cache:
            eff_cache[k] = _eff(groups, t, c)
        return eff_cache[k]

    avail = {}
    for a in plan.availabilities.all():
        avail[(a.teacher_id, a.day, a.period)] = a.available

    fixed_by_cell = {}
    for fl in plan.fixed_lessons.select_related('teacher', 'subject', 'student_class').all():
        key = (fl.student_class_id, fl.day, fl.period)
        fixed_by_cell[key] = {'teacher': fl.teacher_id, 'subject': fl.subject_id,
                              'class': fl.student_class_id}

    lessons = _build_lessons(plan, fixed_by_cell)

    best = None
    for r in range(restarts):
        res = _attempt(plan, seed + r * 7919, iterations, day_names, period_ids,
                       avail, fixed_by_cell, lessons, eff)
        if best is None:
            best = res
        else:
            key_new = (len(res['unscheduled']), -res['hard_score'], -res['soft_score'])
            key_best = (len(best['unscheduled']), -best['hard_score'], -best['soft_score'])
            if key_new < key_best:
                best = res
    return best


def _attempt(plan, seed, iterations, day_names, period_ids, avail, fixed_by_cell,
             lessons, eff):
    random.seed(seed)
    teacher_busy = defaultdict(set)   # (teacher, day, period) -> {class_ids}
    teacher_day = defaultdict(int)
    class_day = defaultdict(int)
    teacher_day_subs = defaultdict(lambda: defaultdict(set))  # (teacher, day) -> {subject: set(periods)}
    teacher_day_seq = defaultdict(list)  # (teacher, day) -> [periods]
    lesson_day_count = defaultdict(int)            # ((teacher, subject, class, day)) -> count
    teacher_period_days = defaultdict(set)  # (teacher, period) -> set(days)
    teacher_day_periods = defaultdict(list)  # (teacher, day) -> [periods]
    grid = {}  # (class, day, period) -> cell

    conflicts = []
    fixed_violation = False

    def can_place(lesson, day, period):
        t, s, c = lesson['teacher'], lesson['subject'], lesson['class']
        ep = eff(t, c)
        if teacher_busy[(t, day, period)]:
            return False
        if (c, day, period) in grid:
            return False
        if avail.get((t, day, period), True) is False:
            return False
        if ep['max_per_day'] is not None:
            if teacher_day[(t, day)] >= ep['max_per_day']:
                return False
            if class_day[(c, day)] >= ep['max_per_day']:
                return False
        if ep['spread_max'] is not None and lesson_day_count[(t, s, c, day)] >= ep['spread_max']:
            return False
        if ep['max_gap'] is not None and _max_gap_run(teacher_day_periods[(t, day)] + [period], period_ids) > ep['max_gap']:
            return False
        if ep['period_repeat']:
            for (pr_period, pr_max) in ep['period_repeat']:
                if period == pr_period and day not in teacher_period_days[(t, period)] and len(teacher_period_days[(t, period)]) >= pr_max:
                    return False
        return True

    # 1) وضع الحصص المثبّتة
    for (c, day, period), fl in fixed_by_cell.items():
        t, s = fl['teacher'], fl['subject']
        if teacher_busy[(t, day, period)]:
            fixed_violation = True
        if (c, day, period) in grid:
            fixed_violation = True
        if avail.get((t, day, period), True) is False:
            fixed_violation = True
        teacher_busy[(t, day, period)].add(c)
        teacher_day[(t, day)] += 1
        class_day[(c, day)] += 1
        teacher_day_subs[(t, day)][s].add(period)
        teacher_day_seq[(t, day)].append(period)
        lesson_day_count[(t, s, c, day)] += 1
        teacher_period_days[(t, period)].add(day)
        teacher_day_periods[(t, day)].append(period)
        grid[(c, day, period)] = dict(fl, fixed=True)

    # 2) ترتيب الحصص الأكثر تقييدًا أولًا
    load_count = defaultdict(int)
    for l in lessons:
        load_count[l['teacher']] += 1
        load_count[l['class']] += 1
    lessons.sort(key=lambda l: -load_count[l['teacher']])

    def slot_cost(lesson, day, period):
        t, s, c = lesson['teacher'], lesson['subject'], lesson['class']
        ep = eff(t, c)
        cost = 0
        seq = sorted(teacher_day_seq[(t, day)] + [period])
        if period in seq:
            i = seq.index(period)
            if i > 0 and i < len(seq) - 1:
                if seq[i] - seq[i - 1] > 1:
                    cost += 3
        if ep['spread_max'] is not None and len(teacher_day_subs[(t, day)][s]) >= ep['spread_max']:
            cost += 4
        cost += teacher_day[(t, day)] * 1
        if ep['max_consecutive']:
            if period - 1 in teacher_day_seq[(t, day)] or period + 1 in teacher_day_seq[(t, day)]:
                run = 1
                p = period - 1
                while p in teacher_day_seq[(t, day)]:
                    run += 1; p -= 1
                p = period + 1
                while p in teacher_day_seq[(t, day)]:
                    run += 1; p += 1
                if run + 1 > ep['max_consecutive']:
                    cost += 5
        if ep['max_gap'] is not None:
            occ = sorted(teacher_day_periods[(t, day)] + [period])
            excess = _max_gap_run(occ, period_ids) - ep['max_gap']
            if excess > 0:
                cost += 6 * excess
        if ep['period_repeat']:
            for (pr_period, pr_max) in ep['period_repeat']:
                if period == pr_period:
                    days_set = teacher_period_days[(t, period)]
                    if day not in days_set and len(days_set) >= pr_max:
                        cost += 6
        if ep['avoid_first_last'] and (period == period_ids[0] or period == period_ids[-1]):
            cost += 2
        return cost

    def block_reason(lesson):
        t, s, c = lesson['teacher'], lesson['subject'], lesson['class']
        ep = eff(t, c)
        reasons = defaultdict(int)
        for day in day_names:
            for period in period_ids:
                if teacher_busy[(t, day, period)]:
                    reasons['المعلم مشغول في نفس الخانة (يُدرّس صفًا آخر)'] += 1; continue
                if (c, day, period) in grid:
                    reasons['الصف مشغول في نفس الخانة (تجاوز سعة الصف = الأيام × الحصص/اليوم)'] += 1; continue
                if avail.get((t, day, period), True) is False:
                    reasons['المعلم غير متاح (التفريغ) في هذه الخانة'] += 1; continue
                if ep['max_per_day'] is not None and teacher_day[(t, day)] >= ep['max_per_day']:
                    reasons['تجاوز أقصى حصص للمعلم في اليوم (%s)' % ep['max_per_day']] += 1; continue
                if ep['max_per_day'] is not None and class_day[(c, day)] >= ep['max_per_day']:
                    reasons['تجاوز أقصى حصص للصف في اليوم'] += 1; continue
                if ep['spread_max'] is not None and lesson_day_count[(t, s, c, day)] >= ep['spread_max']:
                    reasons['تكرار المادة بنفس اليوم أكثر من المسموح'] += 1; continue
                if ep['max_gap'] is not None and _max_gap_run(teacher_day_periods[(t, day)] + [period], period_ids) > ep['max_gap']:
                    reasons['تجاوز أقصى فراغات متتالية للمعلم'] += 1; continue
                if ep['period_repeat']:
                    for (pr_period, pr_max) in ep['period_repeat']:
                        if period == pr_period and day not in teacher_period_days[(t, period)] and len(teacher_period_days[(t, period)]) >= pr_max:
                            reasons['تكرار الحصة بحد أيام للمعلم'] += 1; continue
                return None
        if reasons:
            return max(reasons.items(), key=lambda kv: kv[1])[0]
        return 'لا توجد خانة متاحة مطلقًا'

    unscheduled = []
    for lesson in lessons:
        candidates = []
        for day in day_names:
            for period in period_ids:
                if can_place(lesson, day, period):
                    candidates.append((slot_cost(lesson, day, period), day, period))
        if not candidates:
            unscheduled.append(dict(lesson, reason=block_reason(lesson)))
            continue
        candidates.sort(key=lambda x: (x[0], random.random()))
        _, day, period = candidates[0]
        t, s, c = lesson['teacher'], lesson['subject'], lesson['class']
        teacher_busy[(t, day, period)].add(c)
        teacher_day[(t, day)] += 1
        class_day[(c, day)] += 1
        teacher_day_subs[(t, day)][s].add(period)
        teacher_day_seq[(t, day)].append(period)
        lesson_day_count[(t, s, c, day)] += 1
        teacher_period_days[(t, period)].add(day)
        teacher_day_periods[(t, day)].append(period)
        grid[(c, day, period)] = {'teacher': t, 'subject': s, 'class': c, 'fixed': False}

    # 3) تحسين محلّي (صعود تلّي) يقلّل العقوبة الكلية لقيود المعلمين
    def _swap_ok(a, b):
        (c1, d1, p1), (c2, d2, p2) = a, b
        cell1, cell2 = grid[a], grid[b]
        t1, t2 = cell1['teacher'], cell2['teacher']
        if teacher_busy[(t1, d2, p2)] - {c2}:
            return False
        if teacher_busy[(t2, d1, p1)] - {c1}:
            return False
        if (c1, d2, p2) in grid and grid[(c1, d2, p2)] is not cell2:
            return False
        if (c2, d1, p1) in grid and grid[(c2, d1, p1)] is not cell1:
            return False
        return True

    def _do_swap(a, b):
        (c1, d1, p1), (c2, d2, p2) = a, b
        cell1, cell2 = grid[a], grid[b]
        t1, t2 = cell1['teacher'], cell2['teacher']
        teacher_busy[(t1, d1, p1)].discard(c1)
        teacher_busy[(t2, d2, p2)].discard(c2)
        del grid[a]; del grid[b]
        grid[(c1, d2, p2)] = dict(cell1, fixed=cell1.get('fixed', False))
        grid[(c2, d1, p1)] = dict(cell2, fixed=cell2.get('fixed', False))
        teacher_busy[(t1, d2, p2)].add(c1)
        teacher_busy[(t2, d1, p1)].add(c2)

    keys = list(grid.keys())
    base_pen = _grid_penalty(grid, eff, period_ids)
    for _ in range(iterations):
        keys = list(grid.keys())
        if not keys:
            break
        a = random.choice(keys)
        b = random.choice(keys)
        if a == b:
            continue
        cell1 = grid[a]; cell2 = grid[b]
        if cell1.get('fixed') or cell2.get('fixed'):
            continue
        if not _swap_ok(a, b):
            continue
        c1, d1, p1 = a
        c2, d2, p2 = b
        _do_swap(a, b)
        new_pen = _grid_penalty(grid, eff, period_ids)
        if new_pen <= base_pen or random.random() < 0.03:
            base_pen = new_pen
        else:
            _do_swap((c1, d2, p2), (c2, d1, p1))

    # 4) حساب الدرجات
    total = len(lessons) + len(fixed_by_cell)
    scheduled = len(grid)
    hard_ok = (len(unscheduled) == 0) and (not fixed_violation)
    hard_score = 100.0 if hard_ok else round(100.0 * scheduled / total, 1) if total else 100.0

    soft_score = _soft_score(grid, eff, period_ids)

    entries = []
    for (c, day, period), cell in grid.items():
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


def t_classes_of(grid, t):
    """يستنتج أحد الصفوف المرتبطة بمعلم ضمن الشبكة (لتطبيق قيود النطاق)."""
    for (c, day, period), cell in grid.items():
        if cell['teacher'] == t:
            return c
    return None


def _grid_penalty(grid, eff, period_ids):
    """عقوبة كلية لقيود المعلمين (تُقلّل أثناء البحث المحلّي)."""
    tdp = defaultdict(lambda: defaultdict(list))   # teacher -> day -> [periods]
    tpd = defaultdict(lambda: defaultdict(set))    # teacher -> period -> {days}
    tds = defaultdict(lambda: defaultdict(set))    # teacher -> day -> {subjects}
    for (c, day, period), cell in grid.items():
        if cell.get('fixed'):
            continue
        t = cell['teacher']; s = cell['subject']
        tdp[t][day].append(period)
        tpd[t][period].add(day)
        tds[t][day].add(s)
    pen = 0.0
    for t, by_day in tdp.items():
        for day, ps in by_day.items():
            c = t_classes_of(grid, t)
            ep = eff(t, c)
            ps = sorted(ps)
            if len(ps) >= 2:
                pen += ((ps[-1] - ps[0] + 1) - len(ps)) * 2
            mc = ep['max_consecutive'] or 99
            run = 1
            for i in range(1, len(ps)):
                if ps[i] == ps[i - 1] + 1:
                    run += 1
                else:
                    run = 1
                if run > mc:
                    pen += 1
            if ep['avoid_first_last'] and (ps[0] == period_ids[0] or ps[-1] == period_ids[-1]):
                pen += 1
            if ep['max_gap'] is not None:
                excess = _max_gap_run(ps, period_ids) - ep['max_gap']
                if excess > 0:
                    pen += 3 * excess
            if ep['spread_max'] is not None and len(tds[t][day]) > ep['spread_max']:
                pen += 2 * (len(tds[t][day]) - ep['spread_max'])
    for t, by_p in tpd.items():
        c = t_classes_of(grid, t)
        ep = eff(t, c)
        for period, days in by_p.items():
            for (pr_period, pr_max) in ep['period_repeat']:
                if period == pr_period and len(days) > pr_max:
                    pen += 2 * (len(days) - pr_max)
    return pen


def grid_by_class_day(grid, c, day):
    return [cell for (cc, d, p), cell in grid.items() if cc == c and d == day]


def _soft_score(grid, eff, period_ids):
    if not grid:
        return 100.0
    penalties = 0.0
    teacher_day_periods = defaultdict(lambda: defaultdict(list))
    teacher_day_subs = defaultdict(lambda: defaultdict(set))
    for (c, day, period), cell in grid.items():
        if not cell.get('fixed'):
            t = cell['teacher']; s = cell['subject']
            ep = eff(t, c)
            teacher_day_periods[t][day].append(period)
            teacher_day_subs[t][day].add(s)
            ps = sorted(teacher_day_periods[t][day])
            if len(ps) >= 2:
                gaps = (ps[-1] - ps[0] + 1) - len(ps)
                penalties += gaps * 2
            run = 1
            for i in range(1, len(ps)):
                if ps[i] == ps[i - 1] + 1:
                    run += 1
                else:
                    run = 1
                if run > ep['max_consecutive']:
                    penalties += 1
            if ep['max_gap'] is not None:
                excess = _max_gap_run(ps, period_ids) - ep['max_gap']
                if excess > 0:
                    penalties += 3 * excess
            if ep['avoid_first_last'] and (ps[0] == period_ids[0] or ps[-1] == period_ids[-1]):
                penalties += 1
            if ep['spread_max'] is not None and len(teacher_day_subs[t][day]) > ep['spread_max']:
                penalties += 2 * (len(teacher_day_subs[t][day]) - ep['spread_max'])
    class_day_subs = defaultdict(lambda: defaultdict(set))
    for (c, day, period), cell in grid.items():
        class_day_subs[cell['class']][day].add(cell['subject'])
    for c, by_day in class_day_subs.items():
        for day, subs in by_day.items():
            if len(subs) < len(grid_by_class_day(grid, c, day)):
                penalties += 1
    teacher_period_days = defaultdict(lambda: defaultdict(set))
    for (c, day, period), cell in grid.items():
        if not cell.get('fixed'):
            teacher_period_days[cell['teacher']][period].add(day)
    for t, by_p in teacher_period_days.items():
        for period, days in by_p.items():
            c = t_classes_of(grid, t)
            ep = eff(t, c)
            for (pr_period, pr_max) in ep.get('period_repeat', []):
                if period == pr_period and len(days) > pr_max:
                    penalties += 2 * (len(days) - pr_max)
    for t, by_day in teacher_day_periods.items():
        counts = [len(ps) for ps in by_day.values()]
        if counts:
            avg = sum(counts) / len(counts)
            penalties += sum(abs(c - avg) for c in counts) * 0.3
    max_pen = max(1.0, len(grid) * 0.5)
    return round(max(0.0, 100.0 - (penalties / max_pen) * 100.0), 1)


def evaluate_plan(plan):
    """يعيد تقييم القيود الصلبة والناعمة لبرنامج مولّد أو معدّل يدويًا."""
    entries = list(plan.entries.select_related('teacher', 'subject', 'student_class').all())
    groups = _prepare_constraints(plan)
    period_ids = [p['idx'] for p in plan.active_periods]
    avail = {}
    for a in plan.availabilities.all():
        avail[(a.teacher_id, a.day, a.period)] = a.available
    fixed = {}
    for fl in plan.fixed_lessons.all():
        fixed[(fl.day, fl.period)] = (fl.teacher_id, fl.subject_id, fl.student_class_id)

    teacher_busy = defaultdict(set)  # (teacher, day, period) -> {class}
    class_busy = set()
    conflicts = []

    for e in entries:
        t, c = e.teacher_id, e.student_class_id
        ep = _eff(groups, t, c)
        if teacher_busy[(t, e.day, e.period)]:
            conflicts.append({'type': 'teacher_double', 'day': e.day, 'period': e.period,
                              'teacher': t})
        if (c, e.day, e.period) in class_busy:
            conflicts.append({'type': 'class_double', 'day': e.day, 'period': e.period,
                              'student_class': c})
        teacher_busy[(t, e.day, e.period)].add(c)
        class_busy.add((c, e.day, e.period))
        if avail.get((t, e.day, e.period), True) is False:
            conflicts.append({'type': 'availability', 'day': e.day, 'period': e.period,
                              'teacher': t})
        fk = fixed.get((e.day, e.period))
        if fk and (fk[0] != t or fk[1] != e.subject_id or fk[2] != c):
            conflicts.append({'type': 'fixed_violation', 'day': e.day, 'period': e.period})

    soft_pen = 0
    seq_by_td = defaultdict(list)
    for e in entries:
        seq_by_td[(e.teacher_id, e.student_class_id, e.day)].append(e.period)
    for (t, c, day), ps in seq_by_td.items():
        ep = _eff(groups, t, c)
        ps = sorted(ps)
        run = 1
        for i in range(1, len(ps)):
            if ps[i] == ps[i - 1] + 1:
                run += 1
            else:
                run = 1
            if run > ep['max_consecutive']:
                soft_pen += 1

    spread_map = defaultdict(int)
    for e in entries:
        ep = _eff(groups, e.teacher_id, e.student_class_id)
        if ep['spread_max'] is not None:
            k = (e.teacher_id, e.subject_id, e.student_class_id, e.day)
            spread_map[k] += 1
            if spread_map[k] > ep['spread_max']:
                conflicts.append({'type': 'spread', 'day': e.day, 'teacher': e.teacher_id,
                                  'subject': e.subject_id})
    gap_map = defaultdict(list)
    for e in entries:
        gap_map[(e.teacher_id, e.student_class_id, e.day)].append(e.period)
    for (t, c, day), ps in gap_map.items():
        ep = _eff(groups, t, c)
        if ep['max_gap'] is not None and _max_gap_run(ps, period_ids) > ep['max_gap']:
            conflicts.append({'type': 'gap', 'day': day, 'teacher': t})
    pr_map = defaultdict(set)
    for e in entries:
        pr_map[(e.teacher_id, e.period)].add(e.student_class_id)
    for (t, period), cs in pr_map.items():
        for c in cs:
            ep = _eff(groups, t, c)
            for (pr_period, pr_max) in ep['period_repeat']:
                if period == pr_period:
                    days_count = sum(1 for e in entries
                                     if e.teacher_id == t and e.period == period)
                    if days_count > pr_max:
                        conflicts.append({'type': 'period_repeat', 'period': period, 'teacher': t})

    total = len(entries)
    hard = len(conflicts)
    hard_score = 100.0 if hard == 0 else round(max(0.0, 100.0 - hard * 100.0 / max(total, 1)), 1)
    soft_score = round(max(0.0, 100.0 - soft_pen * 5), 1)
    return {'hard_score': hard_score, 'soft_score': soft_score, 'conflicts': conflicts}
