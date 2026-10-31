import os
import logging

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')

application = get_wsgi_application()

# Never run migrations or database queries during Vercel serverless cold starts.
# Log only the configured provider; the first real request will establish the
# database connection when it actually needs data.
if os.getenv('VERCEL'):
    from django.db import connection

    logger = logging.getLogger(__name__)
    configured_host = (connection.settings_dict.get('HOST') or '').lower()
    provider = (
        'supabase'
        if configured_host.endswith('.supabase.co')
        or configured_host.endswith('.pooler.supabase.com')
        else 'non-supabase'
    )
    logger.warning(
        'DATABASE_CONFIGURATION provider=%s host=%s',
        provider,
        configured_host,
    )
