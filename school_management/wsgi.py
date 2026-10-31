import os
import logging

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')

application = get_wsgi_application()

# Never run migrations during Vercel serverless cold starts. Verify and log
# the selected database safely so production routing can be confirmed.
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
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT current_database(), inet_server_addr()::text, inet_server_port()'
            )
            database_name, server_address, server_port = cursor.fetchone()
        logger.warning(
            'DATABASE_CONNECTION_CHECK provider=%s database=%s host=%s server=%s port=%s',
            provider, database_name, configured_host, server_address, server_port,
        )
    except Exception:
        logger.exception(
            'DATABASE_CONNECTION_CHECK_FAILED provider=%s host=%s',
            provider, configured_host,
        )
