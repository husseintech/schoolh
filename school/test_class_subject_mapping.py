from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Class, Profile, Subject, Teacher
from .teacher_records_models import ClassSubjectMapping


class ClassSubjectMappingTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='admin-map', password='pass12345')
        Profile.objects.create(user=self.admin_user, role='admin')
        self.teacher_user = User.objects.create_user(username='teacher-map', password='pass12345')
        Profile.objects.create(user=self.teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(user=self.teacher_user, full_name='معلم اختبار')
        self.class_one = Class.objects.create(name='صف اختبار 1')
        self.class_two = Class.objects.create(name='صف اختبار 2')
        self.math = Subject.objects.create(name='رياضيات اختبار')
        self.science = Subject.objects.create(name='علوم اختبار')
        self.teacher.classes.add(self.class_one)
        self.teacher.subjects.add(self.math, self.science)
        ClassSubjectMapping.objects.create(student_class=self.class_one, subject=self.math, created_by=self.admin_user)

    def test_teacher_report_shows_only_mapped_subjects_for_assigned_class(self):
        self.client.login(username='teacher-map', password='pass12345')
        response = self.client.get(reverse('academic_achievement_report'), {'class_id': self.class_one.id})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.class_one.name)
        self.assertContains(response, self.math.name)
        self.assertNotContains(response, self.science.name)
        self.assertNotContains(response, self.class_two.name)

    def test_admin_can_save_multiple_subjects_for_class(self):
        self.client.login(username='admin-map', password='pass12345')
        response = self.client.post(reverse('class_subject_mapping'), {
            'class_id': self.class_one.id,
            'subjects': [self.math.id, self.science.id],
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            set(ClassSubjectMapping.objects.filter(student_class=self.class_one).values_list('subject_id', flat=True)),
            {self.math.id, self.science.id},
        )
