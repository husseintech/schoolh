from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.http import HttpResponseNotFound
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from whitenoise.middleware import WhiteNoiseMiddleware

from school.models import (
    Class,
    GuardianSummons,
    Message,
    Notification,
    Profile,
    Student,
    StudentSurvey,
    StudentWarning,
)


class StudentVoiceGuideTests(TestCase):
    def setUp(self):
        self.student_class = Class.objects.create(name='7 أ')
        self.user = User.objects.create_user(username='voice-guide-student', password='safe-password')
        Profile.objects.create(user=self.user, role='student')
        self.student = Student.objects.create(
            user=self.user,
            student_id='409876543',
            full_name='أحمد سالم',
            student_class=self.student_class,
        )
        self.sender = User.objects.create_user(username='voice-guide-sender', password='safe-password')
        Profile.objects.create(user=self.sender, role='admin')

    def test_guide_prioritizes_real_pending_tasks_and_always_links_student_file(self):
        Notification.objects.create(user=self.user, title='إشعار جديد', message='تحديث إداري')
        Message.objects.create(
            sender=self.sender,
            recipient=self.user,
            subject='رسالة جديدة',
            content='يرجى المتابعة',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        tasks = response.context['student_guide_tasks']
        self.assertEqual(
            [task['key'] for task in tasks],
            ['survey', 'notifications', 'messages', 'student_file'],
        )
        self.assertEqual(tasks[0]['url'], reverse('survey_form'))
        self.assertEqual(tasks[-1]['url'], reverse('student_detail', args=[self.student.id]))
        self.assertContains(response, 'student-guide-mascot')
        self.assertContains(response, 'عدم الإظهار اليوم')
        self.assertContains(response, 'استمع')

    def test_completed_survey_is_removed_from_guide_tasks(self):
        StudentSurvey.objects.create(student=self.student)
        self.client.force_login(self.user)

        response = self.client.get(reverse('dashboard'))

        tasks = response.context['student_guide_tasks']
        self.assertEqual([task['key'] for task in tasks], ['student_file'])
        self.assertNotContains(response, 'ابدأ تعبئة المسح')
        self.assertEqual(tasks[0]['title'], 'أحسنت، مهامك مكتملة')

    def test_sensitive_record_details_are_not_spoken_by_guide(self):
        StudentWarning.objects.create(
            student=self.student,
            incident_date='2026-09-10',
            incident_facts='تفاصيل خاصة لا ينبغي نطقها',
            created_by=self.sender,
        )
        GuardianSummons.objects.create(
            student=self.student,
            summons_date='2026-09-11',
            summons_text='سبب استدعاء خاص',
            created_by=self.sender,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('dashboard'))

        file_task = next(task for task in response.context['student_guide_tasks'] if task['key'] == 'student_file')
        self.assertIn('تحديث يحتاج المتابعة', file_task['message'])
        self.assertNotIn('تفاصيل خاصة', file_task['message'])
        self.assertNotIn('سبب استدعاء', file_task['message'])

    def test_voice_guide_is_not_rendered_for_admin_accounts(self):
        self.client.force_login(self.sender)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="studentVoiceGuide"')

    def test_guide_assets_are_collected_as_project_static_files(self):
        self.assertIsNotNone(finders.find('school/img/student-guide-mascot.webp'))
        self.assertIsNotNone(finders.find('school/css/student_voice_guide.css'))
        self.assertIsNotNone(finders.find('school/js/student_voice_guide.js'))

    @override_settings(DEBUG=False, WHITENOISE_USE_FINDERS=True)
    def test_whitenoise_can_serve_guide_assets_without_collectstatic(self):
        middleware = WhiteNoiseMiddleware(lambda request: HttpResponseNotFound())
        response = middleware(RequestFactory().get('/static/school/img/student-guide-mascot.webp'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/webp')
