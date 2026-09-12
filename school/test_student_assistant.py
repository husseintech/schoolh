import json
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from school.models import (
    Class,
    Profile,
    Student,
    StudentAssistantKnowledge,
    StudentAssistantLog,
    StudentAssistantSettings,
)
from school.student_assistant import student_short_name
from school.views import get_clearable_tables


class StudentAssistantTests(TestCase):
    def setUp(self):
        self.student_class = Class.objects.create(name='6 أ')
        self.student_user = User.objects.create_user(username='assistant-student', password='student-pass')
        Profile.objects.create(user=self.student_user, role='student')
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='880001',
            full_name='ليان أحمد محمود حسن',
            student_class=self.student_class,
        )
        self.admin = User.objects.create_user(username='assistant-admin', password='admin-pass')
        Profile.objects.create(user=self.admin, role='admin')
        self.teacher = User.objects.create_user(username='assistant-teacher', password='teacher-pass')
        Profile.objects.create(user=self.teacher, role='teacher')

    def ask(self, question):
        return self.client.post(
            reverse('student_assistant_ask'),
            data=json.dumps({'question': question}),
            content_type='application/json',
        )

    def test_short_name_uses_first_and_second_names_only(self):
        self.assertEqual(student_short_name(self.student.full_name), 'ليان أحمد')
        self.assertNotIn('محمود', student_short_name(self.student.full_name))

    def test_login_redirects_student_to_dashboard_with_immediate_personal_welcome(self):
        response = self.client.post(
            reverse('login'),
            {'username': self.student_user.username, 'password': 'student-pass'},
            follow=True,
        )

        self.assertRedirects(response, reverse('dashboard'))
        config = response.context['student_assistant_config']
        self.assertTrue(config['welcome_pending'])
        self.assertEqual(config['short_name'], 'ليان أحمد')
        self.assertContains(response, 'id="studentAssistantWelcome"')
        self.assertContains(response, 'مساعد المدرسة الذكي')

    def test_assistant_launcher_stays_available_across_student_pages(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('student_absence_report'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="studentGuideLauncher"')
        self.assertFalse(response.context['student_assistant_config']['auto_open'])

    def test_admin_can_disable_assistant_for_all_student_pages(self):
        StudentAssistantSettings.objects.create(enabled=False)
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('dashboard'))

        self.assertNotContains(response, 'id="studentVoiceGuide"')

    def test_guided_stage_answers_from_current_student_data_without_ai(self):
        self.client.force_login(self.student_user)
        with patch('school.student_assistant_views.get_provider') as get_provider:
            response = self.ask('أين أجد جدولي الدراسي؟')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['mode'], 'guided')
        self.assertEqual(payload['action_url'], reverse('dashboard') + '#studentSchedule')
        get_provider.assert_not_called()
        self.assertTrue(StudentAssistantLog.objects.filter(student=self.student, mode='guided').exists())

    def test_service_is_private_to_student_accounts(self):
        self.client.force_login(self.teacher)
        response = self.ask('أين جدولي؟')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(StudentAssistantLog.objects.exists())

    def test_private_identifiers_are_not_sent_to_ai_or_saved_in_logs(self):
        self.client.force_login(self.student_user)
        with patch('school.student_assistant_views.get_provider') as get_provider:
            response = self.ask('رقم هويتي هو 123456789 هل يمكنك حفظه؟')

        self.assertEqual(response.status_code, 200)
        self.assertIn('حرصًا على خصوصيتك', response.json()['answer'])
        get_provider.assert_not_called()
        self.assertFalse(StudentAssistantLog.objects.exists())

    def test_approved_school_knowledge_precedes_ai(self):
        StudentAssistantKnowledge.objects.create(
            title='الطابور الصباحي',
            keywords='الطابور، الاصطفاف',
            answer='يبدأ الطابور الصباحي حسب إعلان إدارة المدرسة.',
            action_label='لوحة الطالب',
            action_url='/dashboard/',
            created_by=self.admin,
        )
        self.client.force_login(self.student_user)
        with patch('school.student_assistant_views.get_provider') as get_provider:
            response = self.ask('متى يبدأ الطابور؟')

        payload = response.json()
        self.assertEqual(payload['mode'], 'knowledge')
        self.assertIn('إدارة المدرسة', payload['answer'])
        get_provider.assert_not_called()

    def test_second_stage_uses_ai_without_sending_student_identity(self):
        provider = Mock()
        provider.answer_student_question.return_value = (
            {'answer': 'الماء يتبخر عندما يكتسب حرارة ويتحول إلى بخار.', 'suggestions': ['ما التكاثف؟']},
            123,
            84,
        )
        self.client.force_login(self.student_user)
        with patch('school.student_assistant_views.get_provider', return_value=provider):
            response = self.ask('اشرح لي عملية التبخر بطريقة سهلة')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mode'], 'ai')
        kwargs = provider.answer_student_question.call_args.kwargs
        self.assertEqual(kwargs['grade'], self.student_class.name)
        self.assertNotIn('student', kwargs)
        self.assertNotIn('ليان', json.dumps(kwargs, ensure_ascii=False))
        log = StudentAssistantLog.objects.get(mode='ai')
        self.assertEqual(log.estimated_tokens, 123)
        self.assertEqual(log.duration_ms, 84)

    def test_daily_ai_limit_does_not_block_guided_help(self):
        StudentAssistantSettings.objects.create(daily_ai_limit=1)
        StudentAssistantLog.objects.create(
            student=self.student,
            question='سؤال سابق',
            answer='إجابة',
            mode='ai',
        )
        self.client.force_login(self.student_user)

        ai_response = self.ask('اشرح لي مفهومًا جديدًا غير معروف')
        guided_response = self.ask('أين أجد جدولي الدراسي؟')

        self.assertEqual(ai_response.status_code, 429)
        self.assertEqual(ai_response.json()['ai_remaining'], 0)
        self.assertEqual(guided_response.status_code, 200)
        self.assertEqual(guided_response.json()['mode'], 'guided')

    def test_recent_exact_ai_answer_is_reused_without_provider_cost(self):
        StudentAssistantLog.objects.create(
            student=self.student,
            question='اشرح دورة الماء',
            answer='إجابة تعليمية محفوظة',
            mode='ai',
        )
        self.client.force_login(self.student_user)
        with patch('school.student_assistant_views.get_provider') as get_provider:
            response = self.ask('اشرح دورة الماء')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mode'], 'cache')
        self.assertEqual(response.json()['answer'], 'إجابة تعليمية محفوظة')
        get_provider.assert_not_called()

    def test_admin_can_manage_settings_and_knowledge_but_teacher_cannot(self):
        self.client.force_login(self.teacher)
        denied = self.client.get(reverse('student_assistant_admin'))
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(denied.url, reverse('dashboard'))

        self.client.force_login(self.admin)
        saved = self.client.post(reverse('student_assistant_admin'), {
            'action': 'save_settings',
            'enabled': 'on',
            'daily_ai_limit': '7',
            'welcome_message': 'أهلًا بك في يوم دراسي جميل.',
        })
        self.assertRedirects(saved, reverse('student_assistant_admin'))
        settings_obj = StudentAssistantSettings.objects.get()
        self.assertTrue(settings_obj.enabled)
        self.assertFalse(settings_obj.educational_ai_enabled)
        self.assertEqual(settings_obj.daily_ai_limit, 7)

        added = self.client.post(reverse('student_assistant_admin'), {
            'action': 'add_knowledge',
            'title': 'المقصف',
            'keywords': 'المقصف، الاستراحة',
            'answer': 'يفتح المقصف في وقت الاستراحة.',
            'action_url': '/dashboard/',
            'action_label': 'العودة للوحة',
            'priority': '20',
        })
        self.assertRedirects(added, reverse('student_assistant_admin'))
        self.assertTrue(StudentAssistantKnowledge.objects.filter(title='المقصف').exists())

    def test_assistant_log_is_available_for_individual_maintenance_flush(self):
        keys = {row[0] for row in get_clearable_tables()}
        self.assertIn('student_assistant_logs', keys)
        StudentAssistantLog.objects.create(student=self.student, question='اختبار', answer='إجابة')
        self.client.force_login(self.admin)

        response = self.client.post(reverse('reset_data'), {
            'action': 'flush_one',
            'key': 'student_assistant_logs',
            'confirm': 'YES',
        })

        self.assertRedirects(response, reverse('reset_data'))
        self.assertFalse(StudentAssistantLog.objects.exists())

    def test_voice_and_chat_assets_are_present(self):
        self.assertIsNotNone(finders.find('school/css/student_voice_guide.css'))
        script_path = finders.find('school/js/student_voice_guide.js')
        self.assertIsNotNone(script_path)
        with open(script_path, encoding='utf-8') as script:
            content = script.read()
        self.assertIn('SpeechSynthesisUtterance', content)
        self.assertIn('SpeechRecognition', content)
        self.assertIn("fetch(config.ask_url", content)
