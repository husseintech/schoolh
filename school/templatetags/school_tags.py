from django import template

register = template.Library()

ARABIC_MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']


@register.filter
def arabic_full_date(value):
    """تنسيق التاريخ مفصل: يوم شهر سنة (مثال: 15 آب 2026)."""
    if not value:
        return ''
    return f'{value.day} {ARABIC_MONTHS[value.month - 1]} {value.year}'


@register.filter
def arabic_month(value):
    """اسم الشهر بالعربية (مثال: أغسطس)."""
    if not value:
        return ''
    return ARABIC_MONTHS[value.month - 1]


@register.filter
def by_name(value, fallback='---'):
    """يعرض اسم المستخدم بأمان حتى لو كان الحساب محذوفاً (None)."""
    if value is None:
        return fallback
    name = (getattr(value, 'get_full_name', None) or (lambda: ''))() or ''
    name = name.strip()
    if not name:
        name = getattr(value, 'username', '')
    return name or fallback


@register.filter
def teacher_full_name(value, fallback='غير محدد'):
    """يعرض الاسم الكامل المرتبط بحساب المعلم، ولا يعرض رقم الهوية كاسم."""
    if value is None:
        return fallback
    try:
        teacher = value.teacher_profile
        if teacher.full_name and teacher.full_name.strip():
            return teacher.full_name.strip()
    except Exception:
        pass

    name = (getattr(value, 'get_full_name', None) or (lambda: ''))()
    name = name.strip() if name else ''
    if name:
        return name

    username = str(getattr(value, 'username', '') or '').strip()
    if username.isdigit():
        return fallback
    return username or fallback


@register.filter
def get_item(value, key):
    """Look up a JSON dictionary key in templates."""
    if not isinstance(value, dict):
        return ''
    return value.get(str(key), value.get(key, ''))
