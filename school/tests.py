from types import SimpleNamespace

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from .middleware import StudentRecordAccessMiddleware


class StudentRecordAccessMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = StudentRecordAccessMiddleware(lambda request: HttpResponse('ok'))

    def test_get_cannot_trigger_protected_mutations(self):
        paths = [
            '/messages/12/delete/',
            '/messages/delete-all/',
            '/visit-program/4/delete/',
            '/whatsapp-groups/3/delete/',
            '/secretary/incoming/7/delete/',
            '/secretary/outgoing/7/delete/',
            '/secretary/no-objection/7/delete/',
            '/followups/8/delete/',
            '/reciprocal-visits/9/delete/',
            '/agenda/10/complete/',
            '/agenda/10/uncomplete/',
            '/agenda/10/delete/',
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self.middleware(self.factory.get(path))
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response['Allow'], 'POST')

    def test_post_is_allowed_to_reach_view(self):
        request = self.factory.post('/agenda/10/complete/')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    def test_admin_can_reach_sensitive_student_report(self):
        request = self.factory.get('/students/5/report/')
        request.user = SimpleNamespace(
            is_authenticated=True,
            profile=SimpleNamespace(role='admin'),
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_student_can_reach_own_detail_lateness_and_survey(self):
        user = SimpleNamespace(
            is_authenticated=True,
            profile=SimpleNamespace(role='student'),
            student_profile=SimpleNamespace(id=5),
        )
        for path in ('/students/5/detail/', '/lateness/student/5/', '/survey/5/'):
            with self.subTest(path=path):
                request = self.factory.get(path)
                request.user = user
                response = self.middleware(request)
                self.assertEqual(response.status_code, 200)
