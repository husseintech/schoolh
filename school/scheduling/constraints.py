import collections

from ortools.sat.python import cp_model as cp

from school.scheduling_engine import _prepare_constraints


def _all_ids(lessons):
    teachers = sorted({l['teacher'] for l in lessons})
    classes = sorted({l['class'] for l in lessons})
    return teachers, classes


def apply_constraints(model, x, lessons, day_names, period_ids, plan):
    """يضيف القيود الصلبة ويبني مصطلحات العقوبة التفضيلية.

    يعيد: (penalties, y_teacher, y_class)
    حيث penalties قائمة من (تعبير_صحيح، وزن).
    """
    groups = _prepare_constraints(plan)
    teachers, classes = _all_ids(lessons)
    penalties = []

    # متغيرات مشتقّة: المعلم/الصف مشغول في الخانة
    y_teacher = {}
    y_class = {}
    for t in teachers:
        for d in day_names:
            for p in period_ids:
                keys = [x[(l['id'], d, p)] for l in lessons if l['teacher'] == t]
                if not keys:
                    continue
                bv = model.NewBoolVar('yt_%d_%s_%s' % (t, d, p))
                model.Add(sum(keys) >= 1).OnlyEnforceIf(bv)
                model.Add(sum(keys) == 0).OnlyEnforceIf(bv.Not())
                y_teacher[(t, d, p)] = bv
    for c in classes:
        for d in day_names:
            for p in period_ids:
                keys = [x[(l['id'], d, p)] for l in lessons if l['class'] == c]
                if not keys:
                    continue
                bv = model.NewBoolVar('yc_%d_%s_%s' % (c, d, p))
                model.Add(sum(keys) >= 1).OnlyEnforceIf(bv)
                model.Add(sum(keys) == 0).OnlyEnforceIf(bv.Not())
                y_class[(c, d, p)] = bv

    _apply_max_periods_per_day(model, x, lessons, day_names, period_ids, groups, teachers, classes, penalties)
    _apply_max_consecutive(model, y_teacher, lessons, day_names, period_ids, groups, teachers, penalties)
    _apply_spread_subject(model, x, lessons, day_names, period_ids, groups, penalties)
    _apply_max_gap(model, y_teacher, lessons, day_names, period_ids, groups, teachers, penalties)
    _apply_period_repeat(model, y_teacher, lessons, day_names, period_ids, groups, teachers, penalties)
    _apply_avoid_first_last(model, y_teacher, lessons, day_names, period_ids, groups, teachers, penalties)
    _apply_balance(model, y_teacher, lessons, day_names, period_ids, teachers, penalties)

    return penalties, y_teacher, y_class


def _cons_of(groups, code, t=None, c=None):
    out = []
    for con in groups.get(code, []):
        if not con.enabled:
            continue
        if con.scope == 'all':
            ok = True
        elif con.scope == 'teachers':
            ok = t is not None and t in con._tids
        elif con.scope == 'classes':
            ok = c is not None and c in con._cids
        else:
            ok = False
        if ok:
            out.append(con)
    return out


def _apply_max_periods_per_day(model, x, lessons, day_names, period_ids, groups, teachers, classes, penalties):
    for con in _cons_of(groups, 'max_periods_per_day'):
        v = int(con.weight)
        hard = (con.type == 'hard')
        for t in teachers:
            applies_t = (con.scope == 'all') or (con.scope == 'teachers' and t in con._tids)
            if not applies_t:
                continue
            for d in day_names:
                expr = sum(x[(l['id'], d, p)] for l in lessons if l['teacher'] == t for p in period_ids)
                if hard:
                    model.Add(expr <= v)
                else:
                    _soft_le(model, expr, v, 4, penalties)
        for c in classes:
            applies_c = (con.scope == 'all') or (con.scope == 'classes' and c in con._cids)
            if not applies_c:
                continue
            for d in day_names:
                expr = sum(x[(l['id'], d, p)] for l in lessons if l['class'] == c for p in period_ids)
                if hard:
                    model.Add(expr <= v)
                else:
                    _soft_le(model, expr, v, 4, penalties)


def _apply_max_consecutive(model, y_teacher, lessons, day_names, period_ids, groups, teachers, penalties):
    for con in _cons_of(groups, 'max_consecutive'):
        k = int(con.weight)
        hard = (con.type == 'hard')
        n = len(period_ids)
        for t in teachers:
            if not (con.scope == 'all' or (con.scope == 'teachers' and t in con._tids)):
                continue
            for d in day_names:
                for i in range(n - k):
                    window = period_ids[i:i + k + 1]
                    expr = sum(y_teacher[(t, d, pp)] for pp in window if (t, d, pp) in y_teacher)
                    if hard:
                        model.Add(expr <= k)
                    else:
                        _soft_le(model, expr, k, 5, penalties)


def _apply_spread_subject(model, x, lessons, day_names, period_ids, groups, penalties):
    for con in _cons_of(groups, 'spread_subject'):
        mx = int((con.params or {}).get('max_per_day', 1))
        hard = (con.type == 'hard')
        for l in lessons:
            applies = (con.scope == 'all') or (con.scope == 'teachers' and l['teacher'] in con._tids) \
                or (con.scope == 'classes' and l['class'] in con._cids)
            if not applies:
                continue
            for d in day_names:
                expr = sum(x[(l['id'], d, p)] for p in period_ids)
                if hard:
                    model.Add(expr <= mx)
                else:
                    _soft_le(model, expr, mx, 4, penalties)


def _apply_max_gap(model, y_teacher, lessons, day_names, period_ids, groups, teachers, penalties):
    for con in _cons_of(groups, 'max_consecutive_gap'):
        g = int((con.params or {}).get('max_gap', 1))
        hard = (con.type == 'hard')
        n = len(period_ids)
        for t in teachers:
            if not (con.scope == 'all' or (con.scope == 'teachers' and t in con._tids)):
                continue
            for d in day_names:
                for i in range(n - g):
                    window = period_ids[i:i + g + 1]
                    expr = sum(y_teacher[(t, d, pp)] for pp in window if (t, d, pp) in y_teacher)
                    if hard:
                        model.Add(expr >= 1)
                    else:
                        absent = model.NewBoolVar('gapabs_%d_%s_%d' % (t, hash(d) % 1000, i))
                        model.Add(expr >= 1).OnlyEnforceIf(absent.Not())
                        model.Add(expr == 0).OnlyEnforceIf(absent)
                        penalties.append((absent, 3))


def _apply_period_repeat(model, y_teacher, lessons, day_names, period_ids, groups, teachers, penalties):
    for con in _cons_of(groups, 'period_repeat'):
        pr = (con.params or {}).get('period')
        mx = int((con.params or {}).get('max_days', 1))
        if pr is None:
            continue
        hard = (con.type == 'hard')
        for t in teachers:
            if not (con.scope == 'all' or (con.scope == 'teachers' and t in con._tids)):
                continue
            expr = sum(y_teacher[(t, d, pr)] for d in day_names if (t, d, pr) in y_teacher)
            if hard:
                model.Add(expr <= mx)
            else:
                _soft_le(model, expr, mx, 3, penalties)


def _apply_avoid_first_last(model, y_teacher, lessons, day_names, period_ids, groups, teachers, penalties):
    for con in _cons_of(groups, 'avoid_first_last'):
        first = period_ids[0]
        last = period_ids[-1]
        for t in teachers:
            if not (con.scope == 'all' or (con.scope == 'teachers' and t in con._tids)):
                continue
            for d in day_names:
                if (t, d, first) in y_teacher:
                    penalties.append((y_teacher[(t, d, first)], 2))
                if (t, d, last) in y_teacher:
                    penalties.append((y_teacher[(t, d, last)], 2))


def _apply_balance(model, y_teacher, lessons, day_names, period_ids, teachers, penalties):
    for t in teachers:
        day_counts = []
        for d in day_names:
            cnt = model.NewIntVar(0, len(period_ids), 'bal_%d_%s' % (t, hash(d) % 1000))
            model.Add(cnt == sum(y_teacher[(t, d, p)] for p in period_ids if (t, d, p) in y_teacher))
            day_counts.append(cnt)
        if len(day_counts) >= 2:
            mx = model.NewIntVar(0, len(period_ids), 'balmx_%d' % t)
            mn = model.NewIntVar(0, len(period_ids), 'balmn_%d' % t)
            model.AddMaxEquality(mx, day_counts)
            model.AddMinEquality(mn, day_counts)
            diff = model.NewIntVar(0, len(period_ids), 'baldiff_%d' % t)
            model.Add(diff == mx - mn)
            penalties.append((diff, 1))


def _soft_le(model, expr, v, weight, penalties):
    if v is None:
        return
    over = model.NewIntVar(0, 100, 'over_%d' % len(penalties))
    model.Add(over >= expr - v)
    penalties.append((over, weight))
