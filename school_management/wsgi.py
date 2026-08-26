import os
import traceback

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')


def make_app():
    try:
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
                    user = User.objects.create_superuser('admin', 'admin@school.com', 'admin123')
                    Profile.objects.create(user=user, role='admin')
            except Exception:
                pass

        return get_wsgi_application()
    except Exception:
        err = traceback.format_exc()

        def error_app(environ, start_response):
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain; charset=utf-8')])
            return [err.encode('utf-8')]

        return error_app


application = make_app()
