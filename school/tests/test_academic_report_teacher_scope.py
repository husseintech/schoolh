from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from school.models import Class, Profile, Subject, Teacher


class AcademicReportTeacherScopeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='teacher_scope', password='pass1234')
        Profile.objects.create(user=self.user, role='teacher')
        self.teacher = Teacher.objects.create(user=self.user, full_name='معلم تجريبي')
        self.class_a = Class.objects.create(name='صف تجريبي أ')
        self.class_b = Class.objects.create(name='صف تجريبي ب')
        self.subject = Subject.objects.create(name='مادة تجريبية')
        self.teacher.classes.add(self.class_a)
        self.teacher.subjects.add(self.subject)
        self.client.login(username='teacher_scope', password='pass1234')

    def test_teacher_sees_assigned_classes_without_schedule(self):
        response = self.client.get(reverse('academic_achievement_report'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.class_a.name)
        self.assertNotContains(response, self.class_b.name)

    def test_teacher_sees_assigned_subject_as_fallback_without_schedule(self):
        response = self.client.get(reverse('academic_achievement_report'), {'class_id': self.class_a.id})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.subject.name)
