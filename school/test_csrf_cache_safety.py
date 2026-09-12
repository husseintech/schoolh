import json

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse

from .models import Class, Profile, Student


class CsrfAndCacheSafetyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='csrf-student', password='safe-password')
        Profile.objects.create(user=self.user, role='student')
        student_class = Class.objects.create(name='صف الحماية')
        Student.objects.create(
            user=self.user,
            student_id='777001',
            full_name='طالب اختبار الحماية',
            student_class=student_class,
        )

    def test_html_pages_are_private_and_never_cached(self):
        response = self.client.get(reverse('home'))

        cache_control = response['Cache-Control']
        self.assertIn('private', cache_control)
        self.assertIn('no-store', cache_control)
        self.assertIn('no-cache', cache_control)

    def test_missing_csrf_redirects_safely_but_does_not_log_user_in(self):
        protected_client = Client(enforce_csrf_checks=True)

        response = protected_client.post(reverse('login'), {
            'username': self.user.username,
            'password': 'safe-password',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home') + '?csrf_refreshed=1')
        self.assertNotIn('_auth_user_id', protected_client.session)
        self.assertIn('no-store', response['Cache-Control'])

    def test_valid_csrf_still_allows_login(self):
        protected_client = Client(enforce_csrf_checks=True)
        protected_client.get(reverse('home'))
        token = protected_client.cookies['csrftoken'].value

        response = protected_client.post(reverse('login'), {
            'username': self.user.username,
            'password': 'safe-password',
            'csrfmiddlewaretoken': token,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
        self.assertEqual(int(protected_client.session['_auth_user_id']), self.user.pk)

    def test_ajax_csrf_failure_returns_safe_json_without_running_request(self):
        protected_client = Client(enforce_csrf_checks=True)
        protected_client.force_login(self.user)

        response = protected_client.post(
            reverse('student_assistant_ask'),
            data=json.dumps({'question': 'أين جدولي؟'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()['csrf_expired'])
        self.assertIn('لم يتم تنفيذ الطلب', response.json()['error'])

    def test_service_worker_caches_static_assets_only(self):
        response = self.client.get(reverse('service_worker'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('schoolm-v2-safe-static', content)
        self.assertIn("e.request.mode === 'navigate'", content)
        self.assertIn("url.pathname.startsWith('/static/')", content)
        self.assertNotIn("CORE = ['/dashboard/'", content)
        self.assertNotIn("caches.match('/dashboard/')", content)
        self.assertIsNotNone(finders.find('pwa/offline.html'))
