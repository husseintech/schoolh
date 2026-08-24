import re

AR_DIGITS = {'٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5',
             '٦': '6', '٧': '7', '٨': '8', '٩': '9'}
ORDINAL = {'الأولى': 1, 'الثانية': 2, 'الثالثة': 3, 'الرابعة': 4, 'الخامسة': 5,
           'السادسة': 6, 'السابعة': 7, 'الثامنة': 8, 'التاسعة': 9, 'العاشرة': 10}


def _norm(text):
    t = str(text)
    for k, v in AR_DIGITS.items():
        t = t.replace(k, v)
    t = t.replace('،', ' ').replace(',', ' ')
    return ' ' + t.strip() + ' '


def _digits(t):
    return [int(n) for n in re.findall(r'\d+', t)]


def _first_num(t):
    nums = _digits(t)
    return nums[0] if nums else None


def _num_near(t, word):
    for m in re.finditer(r'(\d+)\s*' + word, t):
        return int(m.group(1))
    for m in re.finditer(word + r'\s*(\d+)', t):
        return int(m.group(1))
    return None


def parse_constraint_text(text, plan):
    """يحوّل نصًا طبيعيًا (عربي/إنجليزي) إلى قيد قابل للتطبيق. يعيد dict أو None."""
    t = _norm(text)
    tl = plan.teaching_loads.select_related('teacher', 'student_class')
    teacher_ids = []
    class_ids = []
    for row in tl.values_list('teacher__id', 'teacher__full_name', 'student_class__id', 'student_class__name'):
        tid, tname, cid, cname = row
        if tname and tname in text:
            teacher_ids.append(tid)
        if cname and cname in text:
            class_ids.append(cid)
    scope = 'all'
    if teacher_ids:
        scope = 'teachers'
    elif class_ids:
        scope = 'classes'

    type_ = 'soft'
    if any(w in text for w in ['يجب', 'إلزامي', 'ممنوع', 'لا يزيد', 'لا يتجاوز', 'يلتزم', 'إجباري', 'hard']):
        type_ = 'hard'

    code = None
    weight = 1.0
    params = {}
    label = text.strip()[:120]

    if 'تكرار' in text or 'repeat' in t.lower():
        period = None
        for w, v in ORDINAL.items():
            if w in text:
                period = v
                break
        if period is None:
            period = _num_near(t, 'حصة') or _num_near(t, 'lesson')
        if period is None:
            period = 7
        max_days = _num_near(t, 'يوم') or _num_near(t, 'days')
        if max_days is None:
            if 'يومين' in text:
                max_days = 2
            elif any(w in text for w in ['ثلاث', 'ثلاثة']):
                max_days = 3
            elif any(w in text for w in ['أربع', 'اربع', 'أربعة']):
                max_days = 4
            elif 'يوم' in text:
                max_days = 1
            else:
                max_days = 2
        code = 'period_repeat'
        params = {'period': int(period), 'max_days': int(max_days)}
    elif 'متتالية' in text or 'متصلة' in text or 'consecutive' in t.lower():
        num = _num_near(t, 'حصص') or _num_near(t, 'حصة') or _first_num(t) or 2
        code = 'max_consecutive'
        weight = float(num)
    elif 'فراغ' in text or 'فجوة' in text or 'gap' in t.lower():
        num = _num_near(t, 'فراغ') or _first_num(t) or 1
        code = 'max_consecutive_gap'
        params = {'max_gap': int(num)}
    elif any(w in text for w in ['يوميا', 'في اليوم', 'باليوم']) or 'per day' in t.lower() or 'daily' in t.lower():
        num = _num_near(t, 'حصص') or _num_near(t, 'حصة') or _first_num(t) or 4
        code = 'max_periods_per_day'
        weight = float(num)
    elif any(w in text for w in ['توزيع', 'موزعة', 'مرة واحدة يوميا']):
        num = _first_num(t) or 1
        code = 'spread_subject'
        params = {'max_per_day': int(num)}
    elif any(w in text for w in ['تجنب', 'الأولى', 'الأخيرة']) or 'avoid' in t.lower() or 'first' in t.lower() or 'last' in t.lower():
        code = 'avoid_first_last'
    else:
        return None

    return {
        'type': type_, 'code': code, 'label': label, 'weight': weight,
        'params': params, 'scope': scope,
        'teacher_ids': teacher_ids, 'class_ids': class_ids,
    }
