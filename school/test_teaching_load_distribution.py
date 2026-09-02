from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Class, Profile, Subject, Teacher, TeacherScheduleEntry


class TeachingLoadDistributionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='load-admin', password='pass')
        Profile.objects.create(user=self.admin, role='admin')
        teacher_user = User.objects.create_user(username='load-teacher', password='pass')
        Profile.objects.create(user=teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(
            user=teacher_user,
            full_name='معلم اللغة العربية',
            id_number='123456789',
            qualification='بكالوريوس',
            specialization='لغة عربية',
        )
        self.student_class = Class.objects.create(name='4أ')
        self.subject = Subject.objects.create(name='اللغة العربية')
        for period in (1, 2, 3):
            TeacherScheduleEntry.objects.create(
                teacher=self.teacher,
                day='الأحد',
                period=period,
                subject=self.subject,
                student_class=self.student_class,
            )

    def test_admin_report_counts_schedule_periods(self):
        self.client.login(username='load-admin', password='pass')
        response = self.client.get(reverse('teaching_load_distribution'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'معلم اللغة العربية')
        self.assertContains(response, '123456789')
        self.assertContains(response, '4أ')
        self.assertContains(response, 'اللغة العربية')
        self.assertContains(response, '>3<', html=False)

    def test_teacher_cannot_open_administration_report(self):
        self.client.login(username='load-teacher', password='pass')
        response = self.client.get(reverse('teaching_load_distribution'))
        self.assertEqual(response.status_code, 302)
