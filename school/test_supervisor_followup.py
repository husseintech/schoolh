from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile, SupervisorVisit, Teacher
from .supervisor_followup_models import SupervisorVisitFollowup


class SupervisorFollowupWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='followup-admin', password='pass')
        Profile.objects.create(user=self.admin, role='admin')
        teacher_user = User.objects.create_user(username='followup-teacher', password='pass')
        Profile.objects.create(user=teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(user=teacher_user, full_name='معلم اختبار')
        self.visit = SupervisorVisit.objects.create(
            teacher=self.teacher,
            visit_date=date(2026, 9, 1),
            supervisor_name='مشرف اختبار',
            recommendations='توصية للاختبار',
            created_by=self.admin,
        )
        self.client.login(username='followup-admin', password='pass')

    def test_followup_saved_separately_with_date(self):
        response = self.client.post(
            reverse('supervisor_visit_followup', args=[self.visit.id]),
            {'followup_date': '2026-09-05', 'notes': 'تمت المتابعة'},
        )
        self.assertEqual(response.status_code, 302)
        followup = SupervisorVisitFollowup.objects.get(visit=self.visit)
        self.assertEqual(str(followup.followup_date), '2026-09-05')
        self.assertEqual(followup.notes, 'تمت المتابعة')
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.admin_followup, '')

    def test_pending_filter_becomes_followed_after_followup(self):
        report_link = reverse('supervisor_visit_report', args=[self.visit.id])
        pending_url = reverse('supervisor_visit_list') + '?status=pending'
        response = self.client.get(pending_url)
        self.assertContains(response, report_link)
        SupervisorVisitFollowup.objects.create(
            visit=self.visit,
            followup_date=date(2026, 9, 5),
            notes='متابعة',
            created_by=self.admin,
        )
        response = self.client.get(pending_url)
        self.assertNotContains(response, report_link)
        followed_url = reverse('supervisor_visit_list') + '?status=followed'
        response = self.client.get(followed_url)
        self.assertContains(response, report_link)
