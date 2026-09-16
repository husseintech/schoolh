from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Class, Profile, Student, StudentLevel, Subject, Teacher


class StudentLevelsByMonthTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('levels-admin', password='test-pass')
        Profile.objects.create(user=self.admin, role='admin')
        self.student_class = Class.objects.create(name='4أ')
        self.other_class = Class.objects.create(name='4ب')
        self.subject = Subject.objects.create(name='اللغة العربية')
        self.student = self._student('monthly-student', '40001', 'طالب شهري', self.student_class)
        self.other_student = self._student('other-student', '40002', 'طالب صف آخر', self.other_class)
        self.client.force_login(self.admin)

    def _student(self, username, student_id, name, student_class):
        user = User.objects.create_user(username, password='test-pass')
        Profile.objects.create(user=user, role='student')
        return Student.objects.create(
            user=user,
            student_id=student_id,
            full_name=name,
            student_class=student_class,
        )

    def _post_admin_level(self, month, level, student=None, notes=''):
        student = student or self.student
        return self.client.post(reverse('add_student_level'), {
            'class_id': self.student_class.id,
            'subject': self.subject.id,
            'assessment_month': month,
            'student_id': [student.id],
            'level': [level],
            'notes': [notes],
        })

    def test_august_and_september_are_saved_as_separate_levels(self):
        september = self._post_admin_level('2026-09', 'excellent', notes='مستوى أيلول')
        august = self._post_admin_level('2026-08', 'good', notes='مستوى آب')

        self.assertEqual(september.status_code, 302)
        self.assertEqual(august.status_code, 302)
        self.assertEqual(StudentLevel.objects.filter(student=self.student).count(), 2)
        self.assertEqual(
            StudentLevel.objects.get(student=self.student, assessment_month=date(2026, 9, 1)).level,
            'excellent',
        )
        self.assertEqual(
            StudentLevel.objects.get(student=self.student, assessment_month=date(2026, 8, 1)).level,
            'good',
        )

    def test_saving_same_month_updates_without_creating_duplicate(self):
        self._post_admin_level('2026-09', 'good', notes='أول إدخال')
        self._post_admin_level('2026-09', 'very_good', notes='تحديث الشهر')

        levels = StudentLevel.objects.filter(
            student=self.student,
            subject=self.subject,
            assessment_month=date(2026, 9, 1),
        )
        self.assertEqual(levels.count(), 1)
        self.assertEqual(levels.get().level, 'very_good')
        self.assertEqual(levels.get().notes, 'تحديث الشهر')

    def test_posted_student_must_belong_to_selected_class(self):
        response = self._post_admin_level('2026-09', 'excellent', student=self.other_student)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(StudentLevel.objects.filter(student=self.other_student).exists())

    def test_admin_list_and_report_filter_by_assessment_month(self):
        self._post_admin_level('2026-09', 'excellent')
        self._post_admin_level('2026-08', 'good')

        list_response = self.client.get(reverse('student_level_list'), {
            'class_id': self.student_class.id,
            'subject_id': self.subject.id,
            'month': '2026-08',
        })
        report_response = self.client.get(reverse('student_levels_report'), {
            'class_id': self.student_class.id,
            'subject_id': self.subject.id,
            'month': '2026-09',
        })

        self.assertEqual([item.assessment_month for item in list_response.context['levels']], [date(2026, 8, 1)])
        self.assertEqual([item.assessment_month for item in report_response.context['levels']], [date(2026, 9, 1)])
        self.assertContains(report_response, '2026/09')

    def test_teacher_entry_uses_selected_month(self):
        teacher_user = User.objects.create_user('levels-teacher', password='test-pass')
        Profile.objects.create(user=teacher_user, role='teacher')
        teacher = Teacher.objects.create(user=teacher_user, full_name='معلم المستويات')
        teacher.classes.add(self.student_class)
        teacher.subjects.add(self.subject)
        self.client.force_login(teacher_user)
        url = (
            f"{reverse('student_level_list')}?class_id={self.student_class.id}"
            f"&subject_id={self.subject.id}&month=2026-08"
        )

        response = self.client.post(url, {
            'assessment_month': '2026-08',
            f'level_{self.student.id}': 'acceptable',
            f'notes_{self.student.id}': 'مستوى شهر آب',
        })

        self.assertEqual(response.status_code, 302)
        saved = StudentLevel.objects.get(student=self.student, subject=self.subject)
        self.assertEqual(saved.assessment_month, date(2026, 8, 1))
        self.assertEqual(saved.level, 'acceptable')

    def test_add_page_contains_required_month_selector(self):
        response = self.client.get(reverse('add_student_level'), {
            'class_id': self.student_class.id,
        })

        self.assertContains(response, 'name="assessment_month"')
        self.assertContains(response, 'type="month"')
