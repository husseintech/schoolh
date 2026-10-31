import os
import logging

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')

application = get_wsgi_application()

# Fail closed on Vercel unless the application is connected to Supabase.
# Do not run schema migrations during serverless cold starts: migrations must
# be applied deliberately, not on every function initialization.
if os.getenv('VERCEL'):
    from django.db import connection

    configured_host = (connection.settings_dict.get('HOST') or '').lower()
    if not (
        configured_host.endswith('.supabase.co')
        or configured_host.endswith('.pooler.supabase.com')
    ):
        raise RuntimeError(
            'Production database is not configured for Supabase; refusing to start.'
        )

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT current_database(), inet_server_addr()::text, inet_server_port()'
        )
        database_name, server_address, server_port = cursor.fetchone()

    logging.getLogger(__name__).warning(
        'DATABASE_CONNECTION_VERIFIED provider=supabase database=%s host=%s server=%s port=%s',
        database_name,
        configured_host,
        server_address,
        server_port,
    )
