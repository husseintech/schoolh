from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from school.models import Class, Profile, Student, StudentSurvey


class SurveyHealthReportsTests(TestCase):
    def setUp(self):
        self.cls = Class.objects.create(name='4أ')
        self.student_user = User.objects.create_user(username='health-student', password='safe-password')
        Profile.objects.create(user=self.student_user, role='student')
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='409876543',
            full_name='طالب التقرير الصحي',
            student_class=self.cls,
            parent_phone='0599000000',
        )
        self.admin = User.objects.create_user(username='health-admin', password='safe-password')
        Profile.objects.create(user=self.admin, role='admin')
        self.survey = StudentSurvey.objects.create(
            student=self.student,
            chronic_disease=True,
            chronic_disease_details='السكري',
            condition_diabetes=True,
            emergency_instructions='يرجى التواصل مع ولي الأمر عند الحاجة',
        )
        self.client.force_login(self.admin)

    def test_chronic_report_includes_disease_notes_and_student_identity(self):
        response = self.client.get(reverse('survey_stats_print', args=['chronic']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'طالب التقرير الصحي')
        self.assertContains(response, 'السكري')
        self.assertContains(response, '409876543')
        self.assertContains(response, 'يرجى التواصل مع ولي الأمر عند الحاجة')

    def test_official_report_uses_ministry_disease_category_and_parent_phone(self):
        response = self.client.get(reverse('survey_stats_print', args=['official']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'اسم المرض')
        self.assertContains(response, 'رقم الهاتف')
        self.assertContains(response, 'السكري')
        self.assertContains(response, 'طالب التقرير الصحي')
        self.assertContains(response, '0599000000')

    def test_single_disease_report_filters_to_selected_disease(self):
        response = self.client.get(reverse('survey_stats_print', args=['disease']), {'disease': 'السكري'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'طالب التقرير الصحي')
        self.assertContains(response, 'إجمالي الطلاب: 1')

    def test_invalid_disease_is_rejected(self):
        response = self.client.get(reverse('survey_stats_print', args=['disease']), {'disease': 'غير موجود'})
        self.assertRedirects(response, reverse('survey_stats'))
