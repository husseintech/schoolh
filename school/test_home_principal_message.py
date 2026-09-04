from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile, SchoolInfo


class HomePrincipalMessageTests(TestCase):
    def setUp(self):
        SchoolInfo.objects.create(
            name_ar='مدرسة الاختبار الأساسية',
            name_en='Test Basic School',
            principal_name='مدير الاختبار',
            national_number='12345',
        )

    def test_public_home_shows_dynamic_principal_message(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'كلمة مدير المدرسة')
        self.assertContains(response, 'مدير الاختبار')
        self.assertContains(response, 'مدرسة الاختبار الأساسية')
        self.assertContains(response, 'توظّف التكنولوجيا')
        self.assertContains(response, 'أولياء الأمور إلى المتابعة')
        self.assertContains(response, 'data-bs-target="#loginModal"')
        self.assertContains(response, 'id="loginModal"')
        self.assertEqual(response.content.decode().count('name="username"'), 1)

        content = response.content.decode()
        welcome_position = content.index('class="welcome-zone"')
        principal_position = content.index('id="principal-message"')
        quick_links_position = content.index('class="quick-zone"')
        self.assertLess(welcome_position, principal_position)
        self.assertLess(principal_position, quick_links_position)

    def test_authenticated_home_also_shows_principal_message(self):
        admin = User.objects.create_user(username='home-admin', password='safe-password')
        Profile.objects.create(user=admin, role='admin')
        self.client.force_login(admin)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'كلمة مدير المدرسة')
        self.assertContains(response, 'مدير الاختبار')
        self.assertContains(response, 'توظّف التكنولوجيا')
        self.assertContains(response, 'تواصل مع إدارة المدرسة')
        self.assertContains(response, 'فيسبوك المدرسة')
