from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse


class DatabaseHealthTests(TestCase):
    def test_database_health_reports_success_after_real_query(self):
        response = self.client.get(reverse('database_health'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "database": "reachable"},
        )
        self.assertEqual(
            response['Cache-Control'],
            'max-age=0, no-cache, no-store, must-revalidate, private',
        )

    @patch('school.health_views.connection.cursor')
    def test_database_health_hides_database_errors(self, cursor):
        cursor.side_effect = DatabaseError('sensitive database details')

        response = self.client.get(reverse('database_health'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "error", "database": "unreachable"},
        )
        self.assertNotContains(
            response,
            'sensitive database details',
            status_code=503,
        )

    def test_database_health_rejects_post_requests(self):
        response = self.client.post(reverse('database_health'))

        self.assertEqual(response.status_code, 405)
