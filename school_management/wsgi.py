import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')

# Run migrations on Vercel (safe for PostgreSQL)
if os.getenv('VERCEL'):
    import django
    django.setup()
    from django.core.management import call_command
    try:
        call_command('migrate', '--noinput')
    except Exception:
        pass

application = get_wsgi_application()
