from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    InspectionVisit,
    Profile,
    ReciprocalVisit,
    SupervisorVisit,
    Teacher,
    TeacherFollowup,
    UserPermission,
    VisitProgram,
)


class TeacherScopedReportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='scope-admin', password='safe-password')
        Profile.objects.create(user=self.admin, role='admin')

        self.teacher_user = User.objects.create_user(username='scope-teacher', password='safe-password')
        Profile.objects.create(user=self.teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(user=self.teacher_user, full_name='المعلم صاحب الحساب')

        self.other_user = User.objects.create_user(username='scope-other', password='safe-password')
        Profile.objects.create(user=self.other_user, role='teacher')
        self.other_teacher = Teacher.objects.create(user=self.other_user, full_name='المعلم الزميل')

        self.third_user = User.objects.create_user(username='scope-third', password='safe-password')
        Profile.objects.create(user=self.third_user, role='teacher')
        self.third_teacher = Teacher.objects.create(user=self.third_user, full_name='معلم ثالث')

        UserPermission.objects.create(
            user=self.teacher_user,
            permissions={
                'inspection_visits': ['view'],
                'supervisor_visits': ['view'],
                'visit_program': ['view'],
                'teacher_followup': ['view'],
                'reciprocal_visits': ['view'],
            },
        )

        self.own_inspection = InspectionVisit.objects.create(
            teacher=self.teacher,
            visit_date=date(2026, 9, 1),
            lesson_topic='تقرير المعلم نفسه',
        )
        self.other_inspection = InspectionVisit.objects.create(
            teacher=self.other_teacher,
            visit_date=date(2026, 9, 2),
            lesson_topic='تقرير معلم آخر',
        )
        self.own_supervisor = SupervisorVisit.objects.create(
            teacher=self.teacher,
            visit_date=date(2026, 9, 1),
            supervisor_name='مشرف حساب المعلم',
        )
        self.other_supervisor = SupervisorVisit.objects.create(
            teacher=self.other_teacher,
            visit_date=date(2026, 9, 2),
            supervisor_name='مشرف معلم آخر',
        )
        self.own_program = VisitProgram.objects.create(
            teacher=self.teacher,
            visit_date=date(2026, 9, 10),
            lesson='موعد المعلم نفسه',
        )
        self.other_program = VisitProgram.objects.create(
            teacher=self.other_teacher,
            visit_date=date(2026, 9, 11),
            lesson='موعد معلم آخر',
        )
        self.own_followup = TeacherFollowup.objects.create(
            teacher=self.teacher,
            follow_date=date(2026, 9, 1),
            general_notes='متابعة المعلم نفسه',
        )
        self.other_followup = TeacherFollowup.objects.create(
            teacher=self.other_teacher,
            follow_date=date(2026, 9, 1),
            general_notes='متابعة معلم آخر',
        )
        self.participating_visit = ReciprocalVisit.objects.create(
            visitor=self.teacher,
            host=self.other_teacher,
            visit_date=date(2026, 9, 3),
        )
        self.unrelated_visit = ReciprocalVisit.objects.create(
            visitor=self.other_teacher,
            host=self.third_teacher,
            visit_date=date(2026, 9, 4),
        )
        self.client.force_login(self.teacher_user)

    def test_granted_view_permissions_show_only_current_teachers_records(self):
        inspection = self.client.get(reverse('inspection_visit_list'))
        supervisor = self.client.get(reverse('supervisor_visit_list'))
        program = self.client.get(reverse('visit_program_list'))
        followups = self.client.get(reverse('teacher_followups'), {'month': 'all'})
        reciprocal = self.client.get(reverse('reciprocal_visit_list'))

        self.assertEqual(list(inspection.context['visits']), [self.own_inspection])
        self.assertEqual([visit.id for visit in supervisor.context['visits']], [self.own_supervisor.id])
        self.assertEqual(list(program.context['entries']), [self.own_program])
        self.assertEqual(list(followups.context['followups']), [self.own_followup])
        self.assertEqual(list(reciprocal.context['visits']), [self.participating_visit])

    def test_teacher_cannot_open_a_colleagues_report_by_direct_url(self):
        inspection = self.client.get(reverse('inspection_visit_report', args=[self.other_inspection.id]))
        supervisor = self.client.get(reverse('supervisor_visit_report', args=[self.other_supervisor.id]))
        reciprocal = self.client.get(reverse('reciprocal_visit_report', args=[self.unrelated_visit.id]))

        self.assertRedirects(inspection, reverse('dashboard'))
        self.assertRedirects(supervisor, reverse('dashboard'))
        self.assertRedirects(reciprocal, reverse('dashboard'))

    def test_printable_reports_are_scoped_to_current_teacher(self):
        inspection = self.client.get(reverse('inspection_visits_all_report'))
        supervisor = self.client.get(reverse('supervisor_visits_report'))
        program = self.client.get(reverse('visit_program_report'))
        followups = self.client.get(reverse('teacher_followup_report'), {'month': 'all'})
        room = self.client.get(reverse('reciprocal_visits_room_report'))

        self.assertEqual(list(inspection.context['visits']), [self.own_inspection])
        self.assertEqual([visit.id for visit in supervisor.context['visits']], [self.own_supervisor.id])
        self.assertEqual(list(program.context['entries']), [self.own_program])
        self.assertEqual(list(followups.context['followups']), [self.own_followup])
        self.assertEqual(list(room.context['pending']), [self.participating_visit])


class RolePermissionPersistenceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='permissions-admin-2', password='safe-password')
        Profile.objects.create(user=self.admin, role='admin')
        self.teacher_users = []
        for number in range(2):
            user = User.objects.create_user(username=f'permission-teacher-{number}')
            Profile.objects.create(user=user, role='teacher')
            self.teacher_users.append(user)
        self.client.force_login(self.admin)

    def _inspection_view_action(self, response):
        section = next(
            item for item in response.context['permission_sections']
            if item['key'] == 'inspection_visits'
        )
        return next(action for action in section['actions'] if action['key'] == 'view')

    def test_bulk_grant_remains_checked_after_page_refresh(self):
        response = self.client.post(reverse('role_permissions'), {
            'role': 'teacher',
            'action_kind': 'custom',
            'perm_inspection_visits_view': 'on',
        })
        self.assertRedirects(response, f"{reverse('role_permissions')}?role=teacher")

        refreshed = self.client.get(reverse('role_permissions'), {'role': 'teacher'})

        self.assertTrue(self._inspection_view_action(refreshed)['checked'])
        for user in self.teacher_users:
            self.assertEqual(
                UserPermission.objects.get(user=user).permissions['inspection_visits'],
                ['view'],
            )

    def test_bulk_removal_remains_unchecked_after_page_refresh(self):
        for user in self.teacher_users:
            UserPermission.objects.create(
                user=user,
                permissions={'inspection_visits': ['view']},
            )

        self.client.post(reverse('role_permissions'), {
            'role': 'teacher',
            'action_kind': 'custom',
        })
        refreshed = self.client.get(reverse('role_permissions'), {'role': 'teacher'})

        self.assertFalse(self._inspection_view_action(refreshed)['checked'])
        self.assertFalse(self._inspection_view_action(refreshed)['mixed'])
        for user in self.teacher_users:
            self.assertEqual(
                UserPermission.objects.get(user=user).permissions['inspection_visits'],
                [],
            )

    def test_mixed_permission_shows_count_and_assigned_account(self):
        UserPermission.objects.create(
            user=self.teacher_users[0],
            permissions={'inspection_visits': ['view']},
        )

        response = self.client.get(reverse('role_permissions'), {'role': 'teacher'})
        action = self._inspection_view_action(response)

        self.assertTrue(action['mixed'])
        self.assertEqual(action['assigned_count'], 1)
        self.assertEqual(action['total_count'], 2)
        self.assertEqual(action['assigned_users'], [{
            'name': 'permission-teacher-0',
            'username': 'permission-teacher-0',
        }])
        self.assertContains(response, 'عرض الحسابات الممنوحة (1)')
        self.assertContains(response, 'permission-teacher-0')

    def test_untouched_mixed_permission_is_preserved_on_bulk_save(self):
        UserPermission.objects.create(
            user=self.teacher_users[0],
            permissions={'inspection_visits': ['view']},
        )

        self.client.post(reverse('role_permissions'), {
            'role': 'teacher',
            'action_kind': 'custom',
            'preserve_perm_inspection_visits_view': '1',
        })

        first_permissions = UserPermission.objects.get(user=self.teacher_users[0]).permissions
        second_permissions = UserPermission.objects.get(user=self.teacher_users[1]).permissions
        self.assertEqual(first_permissions['inspection_visits'], ['view'])
        self.assertEqual(second_permissions['inspection_visits'], [])
