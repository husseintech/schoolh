from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def database_health(request):
    """Verify that the production application can execute a database query."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            database_value = cursor.fetchone()
    except DatabaseError:
        return JsonResponse(
            {"status": "error", "database": "unreachable"},
            status=503,
        )

    if database_value != (1,):
        return JsonResponse(
            {"status": "error", "database": "unexpected_response"},
            status=503,
        )

    return JsonResponse({"status": "ok", "database": "reachable"})
