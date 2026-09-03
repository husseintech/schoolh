from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from school.models import InspectionVisit, Profile, Teacher, VisitProgram


class VisitNavigationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='visit-admin', password='safe-password')
        Profile.objects.create(user=self.admin, role='admin')

        self.teacher_user = User.objects.create_user(username='visit-teacher', password='safe-password')
        Profile.objects.create(user=self.teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(user=self.teacher_user, full_name='معلم الزيارة')

        self.other_user = User.objects.create_user(username='other-teacher', password='safe-password')
        Profile.objects.create(user=self.other_user, role='teacher')
        self.other_teacher = Teacher.objects.create(user=self.other_user, full_name='معلم آخر')

        self.visit_date = date.today() + timedelta(days=2)
        self.program = VisitProgram.objects.create(
            teacher=self.teacher,
            visit_date=self.visit_date,
            lesson='الحصة الثالثة',
            created_by=self.admin,
        )
        self.report = InspectionVisit.objects.create(
            teacher=self.teacher,
            visit_date=self.visit_date,
            lesson_topic='موضوع تجريبي',
            created_by=self.admin,
        )

    def test_program_link_opens_selected_teacher_and_scheduled_date(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('visit_program_list'))

        expected = (
            f"{reverse('inspection_visit_list')}?teacher_id={self.teacher.id}"
            f"&amp;program_id={self.program.id}#new-inspection-visit"
        )
        self.assertContains(response, expected)

        response = self.client.get(reverse('inspection_visit_list'), {
            'teacher_id': self.teacher.id,
            'program_id': self.program.id,
        })
        self.assertEqual(response.context['selected_teacher'], self.teacher)
        self.assertEqual(response.context['scheduled_visit'], self.program)
        self.assertContains(response, f'value="{self.visit_date.isoformat()}"')

    def test_teacher_sees_report_button_beside_matching_appointment(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('teacher_visits'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('inspection_visit_report', args=[self.report.id]))
        self.assertContains(response, 'مشاهدة تقرير الزيارة')
        self.assertContains(response, 'مشاهدة التقرير')

    def test_teacher_can_view_only_their_own_inspection_report(self):
        other_report = InspectionVisit.objects.create(
            teacher=self.other_teacher,
            visit_date=self.visit_date,
            created_by=self.admin,
        )
        self.client.force_login(self.teacher_user)

        own_response = self.client.get(reverse('inspection_visit_report', args=[self.report.id]))
        other_response = self.client.get(reverse('inspection_visit_report', args=[other_report.id]))

        self.assertEqual(own_response.status_code, 200)
        self.assertRedirects(other_response, reverse('dashboard'))
