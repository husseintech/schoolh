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
        return JsonResponse({"status": "error", "database": "unreachable"}, status=503)

    if database_value != (1,):
        return JsonResponse({"status": "error", "database": "unexpected_response"}, status=503)

    return JsonResponse({"status": "ok", "database": "reachable"})


@require_GET
@never_cache
def kindergarten_schema_health(request):
    """Read-only diagnostic of the kindergarten report table across visible schemas."""
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
                "SELECT current_database(), current_schema(), current_schemas(false)"
            )
            database_name, current_schema, search_path_schemas = cursor.fetchone()

            cursor.execute(
                """
                SELECT table_schema, column_name
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY table_schema, ordinal_position
                """,
                [table_name],
            )
            rows = cursor.fetchall()
    except DatabaseError:
        return JsonResponse(
            {"status": "error", "schema_check": "failed"},
            status=503,
        )

    columns_by_schema = {}
    for schema_name, column_name in rows:
        columns_by_schema.setdefault(schema_name, set()).add(column_name)

    visible_schemas = list(search_path_schemas or [])
    visible_table_schemas = {
        schema: columns_by_schema[schema]
        for schema in visible_schemas
        if schema in columns_by_schema
    }
    visible_columns = set()
    for schema_columns in visible_table_schemas.values():
        visible_columns.update(schema_columns)

    missing_columns = [name for name in required_columns if name not in visible_columns]
    table_visible = bool(visible_table_schemas)
    status = "ok" if table_visible and not missing_columns else "error"

    return JsonResponse(
        {
            "status": status,
            "database": database_name,
            "current_schema": current_schema,
            "search_path_schemas": visible_schemas,
            "table_visible_in_search_path": table_visible,
            "table_schemas_found": {
                schema: {
                    "column_count": len(schema_columns),
                    "required_columns": {
                        name: name in schema_columns for name in required_columns
                    },
                    "missing_columns": [
                        name for name in required_columns if name not in schema_columns
                    ],
                }
                for schema, schema_columns in columns_by_schema.items()
            },
            "missing_columns_in_search_path": missing_columns,
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
