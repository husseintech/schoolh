import json
import os
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from school.models import Class, Profile, Student, Subject, Teacher
from .models import AIUsageLog, LearningLesson
from .services.ai_service import (
    AIServiceUnavailable, GeminiProvider, _base_prompt, lesson_content_hash,
    merge_section, normalize_url, validate_pack,
)
from .services.provider_runtime import get_resilient_provider
from .services.search_service import SearchService, SearchUnavailable


def sample_pack():
    return {
        'objectives': ['يحدد الفاعل المفرد في ثلاث جمل من أربع.', 'يضبط الفاعل بالضمة في جملتين.'],
        'explanation': 'في جملة «قرأَ خالدٌ القصةَ» نبحث عن الشخص الذي قام بالفعل: من قرأ؟ خالدٌ. إذن خالدٌ فاعل مرفوع، وعلامة رفعه الضمة الظاهرة. وفي «رسمتْ سلمى لوحةً» سلمى هي من قامت بالفعل. نبدأ اليوم بالأسماء المفردة ذات الضمة الظاهرة، ولا ندرس العلامات الفرعية.',
        'concepts': ['الفاعل', 'الضمة'],
        'pre_questions': ['من كتب في جملة كتب أحمد؟', 'أي الكلمات تدل على حدث: كتب أم قلم؟'],
        'activities': ['ضع خطًا تحت خالد في قرأ خالد القصة.', 'اضبط عمر في كتب عمر الواجب.'],
        'evaluation_questions': ['حدد الفاعل في كتب عمر الواجب.', 'اضبط الفاعل في رسم أحمد اللوحة.'],
        'interactive_ideas': ['رتب بطاقات قرأ وخالد والقصة.', 'ارفع بطاقة اسم من قام بالفعل عند سماع الجملة.'],
        'external_suggestions': ['ورقة عمل عن الفاعل المفرد والضمة للصف الرابع'],
        'assumptions': ['مثال توضيحي لا يثبت تطابق ترتيب المنهاج.'],
        'worked_examples': [
            {'problem': 'قرأ خالد القصة', 'steps': ['نسأل من قرأ؟', 'خالد هو الذي قرأ.'], 'answer': 'خالدٌ فاعل مرفوع بالضمة.'},
            {'problem': 'كتب عمر الواجب', 'steps': ['نسأل من كتب؟', 'عمر هو الذي كتب.'], 'answer': 'عمرُ فاعل مرفوع بالضمة.'},
        ],
        'misconceptions': [
            {'mistake': 'اعتبار القصة فاعلًا.', 'correction': 'القصة لم تقرأ بل خالد هو الذي قرأ.'},
            {'mistake': 'نصب الفاعل عمر.', 'correction': 'نقول عمرُ لأنه فاعل مرفوع.'},
        ],
        'worksheet': [
            {'question': f'حدد الفاعل واضبطه في المثال {i + 1}.', 'answer': f'إجابة المعلم السرية {i}',
             'hint': 'اسأل من قام بالفعل؟', 'objective_index': i % 2} for i in range(4)
        ],
        'lesson_plan': [
            {'phase': phase, 'minutes': minutes, 'teacher_action': 'يعرض جملة قرأ خالد القصة.',
             'student_action': 'يحدد خالد ويضبطه.', 'assessment': 'يحدد الاسم ويكتب الضمة.', 'objective_index': i % 2}
            for i, (phase, minutes) in enumerate([('تمهيد', 5), ('تطبيق', 25), ('تقويم', 10)])
        ],
    }


BRIEF = {'grade': 4, 'focus': 'تمييز الفاعل المفرد وضبطه بالضمة دون العلامات الفرعية',
         'duration': 40, 'prior_knowledge': 'يميز الاسم والفعل', 'reference_text': '', 'learner_level': 'mixed'}


class AIQualityServiceTests(SimpleTestCase):
    def test_grade_and_focus_are_in_prompt(self):
        base = {'grade': 4, 'subject': 'لغة عربية', 'lesson_title': 'الإعراب', 'brief': BRIEF}
        fourth = _base_prompt(base)
        ninth = _base_prompt({**base, 'grade': 9, 'brief': {**BRIEF, 'grade': 9, 'focus': 'تحليل العلامات الفرعية'}})
        self.assertIn(BRIEF['focus'], fourth)
        self.assertIn('الصف الدراسي: 4', fourth)
        self.assertIn('الصف الدراسي: 9', ninth)
        self.assertNotEqual(fourth, ninth)

    def test_valid_pack_and_invalid_alignment(self):
        validate_pack(sample_pack(), {'brief': BRIEF})
        for mutation in ('time', 'objective', 'generic', 'shape', 'private'):
            with self.subTest(mutation=mutation):
                data = sample_pack()
                if mutation == 'time': data['lesson_plan'][0]['minutes'] = 60
                if mutation == 'objective': data['worksheet'][0]['objective_index'] = 10
                if mutation == 'generic': data['objectives'][0] = 'يشرح المفاهيم الأساسية.'
                if mutation == 'shape': data['worked_examples'] = ['ناقص']
                if mutation == 'private': data['_brief'] = {}
                with self.assertRaises(AIServiceUnavailable):
                    validate_pack(data, {'brief': BRIEF})

    def test_section_cannot_replace_other_fields(self):
        with self.assertRaises(AIServiceUnavailable):
            merge_section(sample_pack(), 'explanation', {'explanation': 'شرح', '_brief': {'grade': 9}})

    def test_no_template_fallback_without_key_or_after_quota(self):
        with patch.dict(os.environ, {'AI_API_KEY': '', 'AI_PROVIDER': ''}):
            self.assertIsNone(get_resilient_provider())
        with patch.dict(os.environ, {'AI_API_KEY': 'secret-test-key', 'AI_PROVIDER': 'gemini'}):
            provider = get_resilient_provider()
        with patch('open_learning.services.ai_service.requests.post', return_value=Mock(status_code=429)):
            with self.assertRaises(AIServiceUnavailable) as error:
                provider.generate_lesson_content({'grade': 4, 'subject': 'عربي', 'lesson_title': 'الفاعل', 'brief': BRIEF})
            self.assertNotIn('secret-test-key', str(error.exception))

    def test_truncated_response_not_saved(self):
        response = Mock(status_code=200)
        response.json.return_value = {'candidates': [{'finishReason': 'MAX_TOKENS', 'content': {'parts': [{'text': '{}'}]}}]}
        with patch('open_learning.services.ai_service.requests.post', return_value=response):
            with self.assertRaises(AIServiceUnavailable):
                GeminiProvider('test')._call('test')

    def test_valid_gemini_response_is_checked(self):
        response = Mock(status_code=200)
        response.json.return_value = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(sample_pack())}]}}]}
        with patch('open_learning.services.ai_service.requests.post', return_value=response):
            data, _, _ = GeminiProvider('test').generate_lesson_content({
                'grade': 4, 'subject': 'عربي', 'lesson_title': 'الفاعل', 'brief': BRIEF})
        self.assertEqual(len(data['worksheet']), 4)

    def test_distinct_video_and_content_ids_survive_normalization(self):
        self.assertNotEqual(normalize_url('https://youtube.com/watch?v=AbC'), normalize_url('https://youtube.com/watch?v=abc'))
        self.assertEqual(normalize_url('https://youtu.be/AbC'), normalize_url('https://www.youtube.com/watch?v=AbC&utm_source=x'))
        self.assertNotEqual(normalize_url('https://example.com/lesson?id=1'), normalize_url('https://example.com/lesson?id=2'))

    def test_search_parser_handles_attribute_order_and_entities(self):
        response = Mock(status_code=200, text="<a href='/l/?uddg=https%3A%2F%2Fexample.com%2Flesson%3Fid%3D1' class='result__a'>إعراب <b>الفاعل</b></a><div class='result__snippet'>شرح &amp; أمثلة</div>")
        with patch('open_learning.services.search_service.requests.get', return_value=response):
            items = SearchService()._search_duckduckgo('فاعل', 4)
        self.assertEqual(items[0]['url'], 'https://example.com/lesson?id=1')
        self.assertEqual(items[0]['snippet'], 'شرح & أمثلة')

    def test_search_all_propagates_failure_and_recognizes_arabic_variants(self):
        service = SearchService()
        with patch.object(service, '_search', side_effect=SearchUnavailable('blocked')):
            with self.assertRaises(SearchUnavailable): service.search_all('الإعراب', '4', 'عربي')
        self.assertTrue(service.is_relevant({'title': 'اعراب الفاعل', 'snippet': ''}, 'الإعراب'))
        self.assertFalse(service.is_relevant({'title': 'كرة القدم', 'snippet': ''}, 'الإعراب'))


class AILearningFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ai-teacher')
        Profile.objects.create(user=self.user, role='teacher')
        self.teacher = Teacher.objects.create(user=self.user, full_name='معلم الاختبار')
        self.grade = Class.objects.create(name='4أ')
        self.subject = Subject.objects.create(name='اللغة العربية')
        self.teacher.classes.add(self.grade)
        self.teacher.subjects.add(self.subject)
        self.lesson = LearningLesson.objects.create(title='الإعراب', teacher=self.teacher, subject=self.subject, status='published')
        self.lesson.student_classes.add(self.grade)
        self.client.force_login(self.user)

    def test_brief_validation_prevents_unspecified_generation(self):
        with patch('open_learning.ai_views.get_provider') as provider:
            response = self.client.post(reverse('open_learning_ai_generate', args=[self.lesson.pk]), {'grade': 30})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['brief_form'].errors)
        provider.assert_not_called()

    def test_generation_is_pending_and_brief_changes_hash(self):
        provider = Mock(name='test', model='test')
        provider.name = 'gemini'
        provider.generate_lesson_content.return_value = (sample_pack(), 100, 200)
        with patch('open_learning.ai_views.get_provider', return_value=provider):
            response = self.client.post(reverse('open_learning_ai_generate', args=[self.lesson.pk]), BRIEF)
        self.assertEqual(response.status_code, 302)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.ai_status, 'pending')
        self.assertEqual(self.lesson.ai_payload['_brief']['grade'], 4)
        self.assertNotEqual(lesson_content_hash(self.lesson), lesson_content_hash(self.lesson, {**BRIEF, 'grade': 9}))

    def test_failure_preserves_previous_content_and_teacher_input(self):
        self.lesson.ai_payload = {'explanation': 'شرح محفوظ'}
        self.lesson.save()
        provider = Mock(model='test')
        provider.name = 'gemini'
        provider.generate_lesson_content.side_effect = AIServiceUnavailable('تعذر الاتصال')
        with patch('open_learning.ai_views.get_provider', return_value=provider):
            response = self.client.post(reverse('open_learning_ai_generate', args=[self.lesson.pk]), BRIEF)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.ai_payload, {'explanation': 'شرح محفوظ'})
        self.assertEqual(response.context['brief_form']['focus'].value(), BRIEF['focus'])

    def test_no_results_is_not_success_and_can_retry(self):
        with patch('open_learning.ai_views.SearchService.search_all', return_value=[]):
            response = self.client.post(reverse('open_learning_ai_search', args=[self.lesson.pk]))
        notices = list(get_messages(response.wsgi_request))
        self.assertTrue(any(m.level_tag == 'warning' for m in notices))
        self.assertFalse(AIUsageLog.objects.filter(lesson=self.lesson, success=True).exists())

    def test_search_outage_is_reported(self):
        with patch('open_learning.ai_views.SearchService.search_all', side_effect=SearchUnavailable('محرك البحث غير متاح')):
            response = self.client.post(reverse('open_learning_ai_search', args=[self.lesson.pk]))
        self.assertIn('محرك البحث غير متاح', ' '.join(str(m) for m in get_messages(response.wsgi_request)))
        self.assertEqual(self.lesson.resources.count(), 0)

    def test_pending_pack_and_teacher_answers_hidden_from_student(self):
        self.lesson.ai_payload = sample_pack()
        self.lesson.ai_status = 'pending'
        self.lesson.save()
        student_user = User.objects.create_user('ai-student')
        Profile.objects.create(user=student_user, role='student')
        Student.objects.create(user=student_user, student_id='999000', full_name='طالب', student_class=self.grade)
        self.client.force_login(student_user)
        url = reverse('open_learning_lesson_detail', args=[self.lesson.pk])
        self.assertNotContains(self.client.get(url), 'ورقة عمل · جرّب بنفسك')
        self.lesson.ai_status = 'approved'
        self.lesson.save()
        response = self.client.get(url)
        self.assertContains(response, 'ورقة عمل · جرّب بنفسك')
        self.assertNotContains(response, 'إجابة المعلم السرية')
        self.assertNotContains(response, 'خطة الحصة · دليل المعلم')
        with patch('open_learning.ai_views.get_provider') as provider:
            response = self.client.post(reverse('open_learning_ai_generate', args=[self.lesson.pk]), BRIEF)
        provider.assert_not_called()
        self.assertEqual(response.status_code, 302)
