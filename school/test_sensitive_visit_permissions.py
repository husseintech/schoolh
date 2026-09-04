import importlib
from datetime import date

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import InspectionVisit, Profile, SupervisorVisit, Teacher, UserPermission


class SensitiveVisitPermissionTests(TestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            username='restricted-teacher',
            password='safe-password',
        )
        Profile.objects.create(user=self.teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            full_name='معلم دون صلاحية زيارات',
        )
        self.client.force_login(self.teacher_user)

    def test_teacher_defaults_cannot_open_visit_management_pages(self):
        supervisor_response = self.client.get(reverse('supervisor_visit_list'))
        inspection_response = self.client.get(reverse('inspection_visit_list'))

        self.assertRedirects(supervisor_response, reverse('dashboard'))
        self.assertRedirects(inspection_response, reverse('dashboard'))

    def test_teacher_without_add_permission_cannot_create_inspection_visit(self):
        UserPermission.objects.create(
            user=self.teacher_user,
            permissions={'inspection_visits': ['view']},
        )

        response = self.client.post(reverse('inspection_visit_list'), {
            'teacher_id': self.teacher.id,
            'visit_date': date.today().isoformat(),
            'lesson_topic': 'محاولة غير مصرح بها',
        })

        self.assertRedirects(response, reverse('inspection_visit_list'))
        self.assertFalse(InspectionVisit.objects.exists())

    def test_explicit_permission_grant_allows_page_access(self):
        UserPermission.objects.create(
            user=self.teacher_user,
            permissions={
                'supervisor_visits': ['view'],
                'inspection_visits': ['view'],
            },
        )

        self.assertEqual(self.client.get(reverse('supervisor_visit_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('inspection_visit_list')).status_code, 200)

    def test_teacher_can_view_only_own_inspection_report_without_management_access(self):
        other_user = User.objects.create_user(username='other-report-teacher')
        Profile.objects.create(user=other_user, role='teacher')
        other_teacher = Teacher.objects.create(user=other_user, full_name='معلم آخر')
        own_visit = InspectionVisit.objects.create(teacher=self.teacher, visit_date=date.today())
        other_visit = InspectionVisit.objects.create(teacher=other_teacher, visit_date=date.today())

        own_response = self.client.get(reverse('inspection_visit_report', args=[own_visit.id]))
        other_response = self.client.get(reverse('inspection_visit_report', args=[other_visit.id]))

        self.assertEqual(own_response.status_code, 200)
        self.assertRedirects(other_response, reverse('dashboard'))

    def test_migration_removes_only_legacy_teacher_visit_permissions(self):
        permissions_row = UserPermission.objects.create(
            user=self.teacher_user,
            permissions={
                'students': ['view'],
                'supervisor_visits': ['view', 'add'],
                'inspection_visits': ['view', 'add', 'edit'],
            },
        )
        migration = importlib.import_module(
            'school.migrations.0049_reset_teacher_visit_permissions'
        )

        migration.remove_legacy_teacher_visit_permissions(apps, None)

        permissions_row.refresh_from_db()
        self.assertEqual(permissions_row.permissions, {'students': ['view']})
