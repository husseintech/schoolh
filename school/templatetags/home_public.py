import re

from django import template

from school.public_models import SchoolPublicSettings

register = template.Library()


@register.simple_tag
def school_home_extras():
    """Expose only the school's real public contact details on the home page."""
    try:
        settings = SchoolPublicSettings.objects.select_related('school_info').first()
    except Exception:
        return {'settings': None, 'whatsapp_number': ''}

    if not settings:
        return {'settings': None, 'whatsapp_number': ''}

    raw_mobile = (settings.school_mobile or '').strip()
    whatsapp_number = ''
    if raw_mobile.startswith('+') or raw_mobile.startswith('00'):
        whatsapp_number = re.sub(r'\D', '', raw_mobile)
        if whatsapp_number.startswith('00'):
            whatsapp_number = whatsapp_number[2:]

    return {
        'settings': settings,
        'whatsapp_number': whatsapp_number,
    }
