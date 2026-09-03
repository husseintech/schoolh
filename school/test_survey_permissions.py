from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from school.forms import StudentSurveyForm
from school.models import Class, Profile, Student, StudentSurvey, UserPermission, has_perm
from school.views import build_survey_stats_data


class SurveyDigitalHealthTests(TestCase):
    def setUp(self):
        self.student_class = Class.objects.create(name='1أ')
        self.user = User.objects.create_user(username='survey-student', password='safe-password')
        Profile.objects.create(user=self.user, role='student')
        self.student = Student.objects.create(
            user=self.user,
            student_id='401234567',
            full_name='طالب المسح',
            student_class=self.student_class,
        )

    def test_digital_health_questions_are_required(self):
        form = StudentSurveyForm(data={'lives_with': 'parents'}, instance=StudentSurvey(student=self.student))

        self.assertFalse(form.is_valid())
        for field in (
            'owns_personal_phone',
            'parent_monitors_content',
            'phone_deprivation_difficulty',
            'unusual_behavior_when_phone_removed',
        ):
            self.assertIn(field, form.errors)

    def test_redesigned_survey_page_renders_all_sections(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('survey_form'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'الصحة العامة')
        self.assertContains(response, 'الحالات والرعاية الصحية')
        self.assertContains(response, 'الصحة الرقمية والعادات المرتبطة بالجوال')
        self.assertContains(response, 'الأسرة والبيئة التعليمية')
        self.assertContains(response, 'ملاحظات الأسرة')

    def test_digital_health_answers_are_saved(self):
        form = StudentSurveyForm(data={
            'lives_with': 'parents',
            'owns_personal_phone': 'True',
            'parent_monitors_content': 'False',
            'phone_deprivation_difficulty': 'True',
            'unusual_behavior_when_phone_removed': 'False',
        }, instance=StudentSurvey(student=self.student))

        self.assertTrue(form.is_valid(), form.errors)
        survey = form.save()
        self.assertIs(survey.owns_personal_phone, True)
        self.assertIs(survey.parent_monitors_content, False)
        self.assertIs(survey.phone_deprivation_difficulty, True)
        self.assertIs(survey.unusual_behavior_when_phone_removed, False)

    def test_old_unanswered_surveys_are_not_counted_as_no(self):
        StudentSurvey.objects.create(student=self.student)

        data = build_survey_stats_data()

        for row in data['digital_rows']:
            self.assertEqual(row['answered'], 0)
            self.assertEqual(row['count'], 0)

    def test_dashboard_prompts_until_survey_is_completed(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'صحتك وراحتك تهمّنا')
        self.assertContains(response, 'بعد إكمال الاستمارة ستظهر روابط مجموعات واتساب')

        StudentSurvey.objects.create(student=self.student)
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'id="surveyReminderModal"')


class PermissionBaselineTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='permissions-admin', password='safe-password')
        Profile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

    def test_account_without_custom_row_uses_role_defaults(self):
        student_user = User.objects.create_user(username='no-permission-row', password='safe-password')
        Profile.objects.create(user=student_user, role='student')

        self.assertTrue(has_perm(student_user, 'open_learning', 'view'))
        self.assertTrue(has_perm(student_user, 'survey', 'add'))

    def test_role_page_starts_with_role_defaults_selected(self):
        response = self.client.get(reverse('role_permissions'), {'role': 'student'})

        sections = response.context['permission_sections']
        checked = {
            action['token']
            for section in sections
            for action in section['actions']
            if action['checked']
        }
        self.assertIn('open_learning_view', checked)
        self.assertIn('survey_add', checked)

    def test_batch_save_can_explicitly_remove_a_whole_module(self):
        student_user = User.objects.create_user(username='batch-student', password='safe-password')
        Profile.objects.create(user=student_user, role='student')

        response = self.client.post(reverse('role_permissions'), {
            'role': 'student',
            'action_kind': 'custom',
            'perm_survey_add': 'on',
        })

        self.assertEqual(response.status_code, 302)
        permissions = UserPermission.objects.get(user=student_user).permissions
        self.assertEqual(permissions['survey'], ['add'])
        self.assertEqual(permissions['open_learning'], [])
        self.assertFalse(has_perm(student_user, 'open_learning', 'view'))

    def test_edit_page_shows_effective_legacy_permissions(self):
        student_user = User.objects.create_user(username='legacy-student', password='safe-password')
        Profile.objects.create(user=student_user, role='student')
        UserPermission.objects.create(user=student_user, permissions={'survey': ['add']})

        response = self.client.get(reverse('edit_account', args=[student_user.id]))

        sections = response.context['permission_sections']
        checked = {
            action['token']
            for section in sections
            for action in section['actions']
            if action['checked']
        }
        self.assertIn('open_learning_view', checked)
