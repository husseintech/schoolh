from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Class, LoginEvent, Profile, Student, Teacher


class LoginReportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='login-admin', password='safe-password')
        Profile.objects.create(user=self.admin, role='admin')

        self.teacher_user = User.objects.create_user(username='teacher-login', password='safe-password')
        Profile.objects.create(user=self.teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            full_name='المعلم النشيط',
            id_number='900001',
        )

        self.other_teacher_user = User.objects.create_user(username='other-teacher', password='safe-password')
        Profile.objects.create(user=self.other_teacher_user, role='teacher')
        self.other_teacher = Teacher.objects.create(
            user=self.other_teacher_user,
            full_name='المعلم الآخر',
            id_number='900002',
        )

        student_class = Class.objects.create(name='الخامس أ')
        self.student_user = User.objects.create_user(username='student-login', password='safe-password')
        Profile.objects.create(user=self.student_user, role='student')
        self.student = Student.objects.create(
            user=self.student_user,
            full_name='الطالب النشيط',
            student_id='800001',
            student_class=student_class,
        )

    def test_successful_teacher_and_student_logins_are_recorded(self):
        response = self.client.post(reverse('login'), {
            'username': self.teacher_user.username,
            'password': 'safe-password',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(LoginEvent.objects.filter(user=self.teacher_user, role='teacher').count(), 1)

        self.client.get(reverse('logout'))
        self.client.post(reverse('login'), {
            'username': self.student_user.username,
            'password': 'safe-password',
        })
        self.assertEqual(LoginEvent.objects.filter(user=self.student_user, role='student').count(), 1)

    def test_report_lists_all_accounts_without_search(self):
        LoginEvent.objects.create(user=self.teacher_user, role='teacher')
        LoginEvent.objects.create(user=self.student_user, role='student')
        self.client.force_login(self.admin)

        response = self.client.get(reverse('login_report'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.teacher.full_name)
        self.assertContains(response, self.other_teacher.full_name)
        self.assertContains(response, self.student.full_name)
        self.assertContains(response, 'الأكثر دخولًا من المعلمين')
        self.assertContains(response, 'الأكثر دخولًا من الطلاب')

    def test_search_only_filters_the_full_lists(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('login_report'), {'q': self.teacher.id_number})

        self.assertContains(response, self.teacher.full_name)
        self.assertNotContains(response, self.other_teacher.full_name)
        self.assertNotContains(response, self.student.full_name)

    def test_account_report_shows_count_and_login_times(self):
        first_time = timezone.now() - timedelta(days=1)
        LoginEvent.objects.create(user=self.teacher_user, role='teacher', logged_at=first_time)
        LoginEvent.objects.create(user=self.teacher_user, role='teacher')
        self.client.force_login(self.admin)

        response = self.client.get(reverse('login_report_detail', args=[self.teacher_user.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.teacher.full_name)
        self.assertContains(response, 'إجمالي مرات الدخول')
        self.assertContains(response, '2')
        self.assertEqual(response.context['login_count'], 2)

    def test_non_admin_cannot_open_login_reports(self):
        self.client.force_login(self.teacher_user)

        list_response = self.client.get(reverse('login_report'))
        detail_response = self.client.get(reverse('login_report_detail', args=[self.student_user.id]))

        self.assertRedirects(list_response, reverse('dashboard'))
        self.assertRedirects(detail_response, reverse('dashboard'))
