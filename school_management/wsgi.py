import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')

# Run migrations and setup on Vercel
if os.getenv('VERCEL'):
    import django
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth.models import User
    from school.models import Profile
    try:
        call_command('migrate', '--noinput')
        if not User.objects.filter(username='admin').exists():
            # Load backup data if file exists next to wsgi.py
            import json
            from pathlib import Path
            backup = Path(__file__).parent.parent / 'data.json'
            if backup.exists():
                call_command('loaddata', str(backup))
                backup.unlink(missing_ok=True)
            else:
                user = User.objects.create_superuser('admin', 'admin@school.com', 'admin123')
                Profile.objects.create(user=user, role='admin')
    except Exception:
        pass

application = get_wsgi_application()
