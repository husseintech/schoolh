from django import template

register = template.Library()

ARABIC_MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']


@register.filter
def arabic_full_date(value):
    """تنسيق التاريخ مفصل: يوم شهر سنة (مثال: 15 آب 2026)."""
    if not value:
        return ''
    return f'{value.day} {ARABIC_MONTHS[value.month - 1]} {value.year}'
