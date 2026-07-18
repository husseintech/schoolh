import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_whatsapp_message(phone_number, message):
    provider = settings.WHATSAPP_PROVIDER
    if provider == 'ultramsg':
        return _send_ultramsg(phone_number, message)
    elif provider == 'log':
        return _log_message(phone_number, message)
    else:
        logger.warning(f'WhatsApp provider "{provider}" غير معروف')
        return False


def _send_ultramsg(phone_number, message):
    token = settings.ULTRAMSG_TOKEN
    instance_id = settings.ULTRAMSG_INSTANCE_ID
    if not token or not instance_id:
        logger.warning('ULTRAMSG_TOKEN أو ULTRAMSG_INSTANCE_ID غير معرفين')
        return False

    phone = phone_number
    if phone.startswith('0'):
        phone = phone[1:]
    if not phone.startswith('+'):
        phone = '+' + phone

    url = f'https://api.ultramsg.com/{instance_id}/messages/chat'
    payload = {
        'token': token,
        'to': phone,
        'body': message,
    }
    try:
        resp = requests.post(url, data=payload, timeout=15)
        if resp.status_code == 200:
            logger.info(f'تم إرسال واتساب إلى {phone}')
            return True
        else:
            logger.error(f'فشل إرسال واتساب: {resp.status_code} - {resp.text}')
            return False
    except requests.RequestException as e:
        logger.error(f'خطأ في الاتصال بخدمة واتساب: {e}')
        return False


def _log_message(phone_number, message):
    logger.info(f'[واتساب تجريبي] إلى {phone_number}: {message}')
    print(f'\n--- رسالة واتساب (تجريبي) ---')
    print(f'الرقم: {phone_number}')
    print(f'الرسالة: {message}')
    print(f'---\n')
    return True
