from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from school.models import HealthCommitteeRecord, Profile, UserPermission


class HealthCommitteeAccessTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='health-admin', password='safe-password')
        Profile.objects.create(user=self.admin, role='admin')
        self.teacher = User.objects.create_user(username='health-teacher', password='safe-password')
        Profile.objects.create(user=self.teacher, role='teacher')

    def test_admin_can_open_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('health_committee_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ملف اللجنة الصحية المدرسية')

    def test_teacher_without_permission_is_denied(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('health_committee_dashboard'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_invalid_activity_participant_count_does_not_crash(self):
        UserPermission.objects.create(
            user=self.teacher,
            permissions={'health_committee': ['view', 'add']},
        )
        self.client.force_login(self.teacher)
        response = self.client.post(reverse('health_committee_record_add'), {
            'title': 'نشاط توعوي',
            'record_type': 'activity',
            'record_date': '2026-10-11',
            'status': 'planned',
            'activity_participants_count': 'غير صالح',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'عدد مشاركين صحيح')
        self.assertFalse(HealthCommitteeRecord.objects.filter(title='نشاط توعوي').exists())

    def test_user_with_explicit_permissions_can_create_record(self):
        UserPermission.objects.create(
            user=self.teacher,
            permissions={'health_committee': ['view', 'add']},
        )
        self.client.force_login(self.teacher)
        response = self.client.post(reverse('health_committee_record_add'), {
            'title': 'جولة فحص السلامة',
            'record_type': 'safety',
            'record_date': '2026-10-11',
            'status': 'planned',
        })
        self.assertRedirects(response, reverse('health_committee_dashboard'))
        self.assertTrue(HealthCommitteeRecord.objects.filter(title='جولة فحص السلامة').exists())
