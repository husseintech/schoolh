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
