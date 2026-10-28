import os

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


@require_GET
@never_cache
def kindergarten_schema_health(request):
    """Read-only check of required columns using the live app DB connection."""
    table_name = "school_kindergartenvisitreport"
    required_columns = (
        "scientific_qualification",
        "professional_qualification",
        "whole_group_count",
        "small_group_count",
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
                  AND table_schema = ANY(current_schemas(false))
                """,
                [table_name],
            )
            columns = {row[0] for row in cursor.fetchall()}
    except DatabaseError:
        return JsonResponse(
            {"status": "error", "table": table_name, "schema_check": "failed"},
            status=503,
        )

    table_exists = bool(columns)
    missing_columns = [name for name in required_columns if name not in columns]
    status = "ok" if table_exists and not missing_columns else "error"

    return JsonResponse(
        {
            "status": status,
            "table_exists": table_exists,
            "required_columns": {name: name in columns for name in required_columns},
            "missing_columns": missing_columns,
        },
        status=200 if status == "ok" else 503,
    )


@require_GET
def database_heartbeat(request):
    """Lightweight, read-only database heartbeat used by the scheduled job."""
    expected_secret = os.getenv("CRON_SECRET")
    if not expected_secret or request.headers.get("Authorization") != f"Bearer {expected_secret}":
        return JsonResponse({"status": "forbidden"}, status=403)

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            database_value = cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "error", "database": "unreachable"}, status=503)

    if database_value != (1,):
        return JsonResponse({"status": "error", "database": "unexpected_response"}, status=503)

    return JsonResponse({"status": "ok", "database": "reachable"})
