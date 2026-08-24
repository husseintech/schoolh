import time

from ortools.sat.python import cp_model

from school.scheduling.constraints import apply_constraints
from school.scheduling.objective import assemble
from school.scheduling.diagnostics import pre_validate


def _build_lessons(plan):
    sem = (plan.semester or '').strip()
    lessons = []
    for tl in plan.teaching_loads.select_related('teacher', 'subject', 'student_class').all():
        if sem and tl.semester and tl.semester != sem:
            continue
        lessons.append({
            'id': tl.id,
            'teacher': tl.teacher_id,
            'subject': tl.subject_id,
            'class': tl.student_class_id,
            'required': int(tl.weekly_periods),
        })
    return lessons


def generate_schedule_cp(plan, max_time=30, seed=0):
    t0 = time.time()
    day_names = [d['name'] for d in plan.active_days]
    period_ids = [p['idx'] for p in plan.active_periods]
    lessons = _build_lessons(plan)
    required_total = sum(l['required'] for l in lessons)

    diag = pre_validate(plan, lessons, day_names, period_ids)
    if diag:
        return {
            'status': 'INFEASIBLE',
            'solver_status': 'INFEASIBLE',
            'entries': [],
            'unscheduled': [],
            'hard_violations': None,
            'soft_score': 0.0,
            'solver_time': 0.0,
            'diagnostics': diag,
            'stats': {
                'required': required_total,
                'scheduled': 0,
                'days': len(day_names),
                'periods': len(period_ids),
            },
        }

    model = cp_model.CpModel()
    x = {}
    for l in lessons:
        for d in day_names:
            for p in period_ids:
                x[(l['id'], d, p)] = model.NewBoolVar('x_%d_%s_%s' % (l['id'], d, p))

    # القيود الصلبة الأساسية
    # عدم تداخل المعلم
    tmap = {}
    cmap = {}
    for l in lessons:
        tmap.setdefault((l['teacher'],), []).append(l)
        cmap.setdefault((l['class'],), []).append(l)
    for t, ls in tmap.items():
        for d in day_names:
            for p in period_ids:
                keys = [x[(l['id'], d, p)] for l in ls]
                model.Add(sum(keys) <= 1)
    for c, ls in cmap.items():
        for d in day_names:
            for p in period_ids:
                keys = [x[(l['id'], d, p)] for l in ls]
                model.Add(sum(keys) <= 1)

    # النصاب الدقيق
    for l in lessons:
        model.Add(sum(x[(l['id'], d, p)] for d in day_names for p in period_ids) == l['required'])

    # التفريغ
    avail_unavail = {(a.teacher_id, a.day, a.period) for a in plan.availabilities.all() if a.available is False}
    for (t, d, p) in avail_unavail:
        keys = [x[(l['id'], d, p)] for l in lessons if l['teacher'] == t]
        if keys:
            model.Add(sum(keys) == 0)

    # الحصص المثبتة
    tl_index = {(l['teacher'], l['subject'], l['class']): l['id'] for l in lessons}
    for fl in plan.fixed_lessons.select_related('teacher', 'subject', 'student_class').all():
        tid = tl_index.get((fl.teacher_id, fl.subject_id, fl.student_class_id))
        if tid is not None:
            model.Add(x[(tid, fl.day, fl.period)] == 1)

    # القيود من ScheduleConstraint
    penalties, _, _ = apply_constraints(model, x, lessons, day_names, period_ids, plan)
    assemble(model, penalties)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_time
    solver.parameters.random_seed = seed
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)
    st = solver.StatusName(status)
    elapsed = time.time() - t0

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        entries = []
        for l in lessons:
            for d in day_names:
                for p in period_ids:
                    if solver.Value(x[(l['id'], d, p)]) == 1:
                        entries.append({
                            'day': d,
                            'period': p,
                            'teacher': l['teacher'],
                            'subject': l['subject'],
                            'class': l['class'],
                            'fixed': False,
                        })
        # وسم الحصص المثبتة
        fixed_cells = {(fl.teacher_id, fl.subject_id, fl.student_class_id, fl.day, fl.period)
                       for fl in plan.fixed_lessons.all()}
        for e in entries:
            if (e['teacher'], e['subject'], e['class'], e['day'], e['period']) in fixed_cells:
                e['fixed'] = True
        return {
            'status': 'SUCCESS' if status == cp_model.OPTIMAL else 'FEASIBLE',
            'solver_status': st,
            'entries': entries,
            'unscheduled': [],
            'hard_violations': 0,
            'soft_score': float(solver.ObjectiveValue()) if penalties else 0.0,
            'solver_time': elapsed,
            'diagnostics': [],
            'stats': {
                'required': required_total,
                'scheduled': len(entries),
                'days': len(day_names),
                'periods': len(period_ids),
            },
        }

    return {
        'status': 'INFEASIBLE' if status == cp_model.INFEASIBLE else 'UNKNOWN',
        'solver_status': st,
        'entries': [],
        'unscheduled': [],
        'hard_violations': None,
        'soft_score': 0.0,
        'solver_time': elapsed,
        'diagnostics': ['لم يجد Solver حلًا صالحًا (الحالة: %s). راجع النصاب/التفريغ/الحصص المثبتة.' % st],
        'stats': {
            'required': required_total,
            'scheduled': 0,
            'days': len(day_names),
            'periods': len(period_ids),
        },
    }
