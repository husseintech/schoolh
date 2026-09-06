import os
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from school.models import Profile, Student, Teacher

from . import test_ai_quality as quality
from .services.open_sources import CATALOGS, CatalogUnavailable, catalog_search, teacher_search_links
from .services.search_service import SearchService, SearchUnavailable, lesson_search_topics


def api_response(rows):
    response = Mock(status_code=200)
    response.json.return_value = {'query': {'search': rows}}
    return response


class OpenCatalogTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_default_is_keyless_catalog(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(SearchService().provider, 'open_catalog')

    def test_second_grade_review_accepts_individual_concepts_not_political_movements(self):
        title = 'مراجعة عامة للحروف ، مع الحركات وحروف المد'
        topics = lesson_search_topics(title, 'اللغة العربية')
        self.assertIn('أبجدية عربية', topics)
        self.assertIn('تشكيل لغة', topics)
        self.assertIn('حروف المد', topics)
        self.assertFalse(any('مراجعة' in topic for topic in topics))
        items = [
            {'title': 'أبجدية عربية', 'snippet': 'الحروف الهجائية'},
            {'title': 'تشكيل (لغة)', 'snippet': 'الفتحة والضمة والكسرة'},
            {'title': 'حروف المد', 'snippet': 'الألف والواو والياء'},
            {'title': 'الحركات السياسية', 'snippet': 'مراجعة عامة للحركات'},
            {'title': 'حروف الجر', 'snippet': 'حروف اللغة العربية'},
        ]
        service = SearchService()
        service.provider = 'open_catalog'
        with patch('open_learning.services.open_sources.catalog_search', side_effect=[items, [], []]) as search:
            results = service.search_all(title, '2', 'اللغة العربية')
        self.assertEqual(results, items[:3])
        self.assertEqual(search.call_count, 3)

    def test_compound_queries_are_quoted_and_cannot_inject_search_operators(self):
        with patch('open_learning.services.open_sources.requests.get', return_value=api_response([])) as get:
            catalog_search(*CATALOGS[0], ['حروف المد', 'الحركات القصيرة', '" OR insource:test'])
        query = get.call_args.kwargs['params']['srsearch']
        self.assertEqual(query, '"حروف المد" OR "الحركات القصيرة" OR "OR insource test"')

    def test_arabic_letter_aliases_are_not_used_for_other_subjects(self):
        self.assertEqual(lesson_search_topics('الحركات', 'العلوم'), ['الحركات'])
        self.assertEqual(lesson_search_topics('دورة الماء', 'العلوم'), ['دورة الماء'])

    def test_canonical_page_link_and_cache(self):
        response = api_response([{'pageid': 321, 'title': 'الفاعل', 'snippet': '<span>الفاعل</span> &amp; إعرابه'}])
        with patch('open_learning.services.open_sources.requests.get', return_value=response) as get:
            first = catalog_search(*CATALOGS[0], 'الفاعل')
            second = catalog_search(*CATALOGS[0], 'الفاعل')
        self.assertEqual(first, second)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(first[0]['url'], 'https://ar.wikipedia.org/?curid=321')
        self.assertEqual(first[0]['snippet'], 'الفاعل & إعرابه')
        self.assertIn('SchoolhLearningSources', get.call_args.kwargs['headers']['User-Agent'])
        self.assertNotIn('key', get.call_args.kwargs['params'])

    def test_invalid_page_ids_not_imported(self):
        response = api_response([{'title': 'الفاعل', 'pageid': 'javascript:alert(1)'}, {'title': 'الفاعل', 'pageid': -1}])
        with patch('open_learning.services.open_sources.requests.get', return_value=response):
            self.assertEqual(catalog_search(*CATALOGS[0], 'الفاعل'), [])

    def test_zero_results_different_from_connection_error(self):
        with patch('open_learning.services.open_sources.requests.get', return_value=api_response([])):
            self.assertEqual(catalog_search(*CATALOGS[0], 'الفاعل'), [])
        cache.clear()
        with patch('open_learning.services.open_sources.requests.get', return_value=Mock(status_code=429)):
            with self.assertRaises(CatalogUnavailable):
                catalog_search(*CATALOGS[0], 'الفاعل')

    def test_partial_library_failure_preserves_relevant_results(self):
        item = {'title': 'الفاعل', 'url': 'https://ar.wikipedia.org/?curid=321', 'snippet': 'الفاعل في الإعراب', 'group': 'reading', 'catalog_reference': True}
        service = SearchService()
        service.provider = 'open_catalog'
        with patch('open_learning.services.open_sources.catalog_search', side_effect=[[item], CatalogUnavailable('تعذر'), []]):
            self.assertEqual(service.search_all('الفاعل', '4', 'عربي'), [item])
        self.assertEqual(len(service.warnings), 1)
        with patch('open_learning.services.open_sources.catalog_search', side_effect=CatalogUnavailable('تعذر')):
            with self.assertRaises(SearchUnavailable): service.search_all('الفاعل', '4', 'عربي')

    def test_reference_description_does_not_claim_grade_alignment(self):
        data = SearchService().classify({'title': 'الفاعل', 'url': 'https://ar.wikipedia.org/?curid=321',
            'snippet': 'شرح الفاعل', 'group': 'reading', 'catalog_name': 'ويكيبيديا العربية', 'catalog_reference': True}, 'الفاعل', '4', 'عربي')
        self.assertIn('ليس درسًا مخصصًا للصف', data['description'])
        self.assertEqual(data['source_name'], 'ويكيبيديا العربية')


class FreeSourcesFlowTests(TestCase):
    setUp = quality.AILearningFlowTests.setUp

    def test_search_page_offers_manual_paths_without_running_search(self):
        with patch('open_learning.ai_views.SearchService.search_all') as search:
            response = self.client.get(reverse('open_learning_ai_search', args=[self.lesson.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ليست مصادر عثر عليها النظام')
        self.assertContains(response, 'حفظ المصدر للمراجعة')
        search.assert_not_called()

    def test_guided_video_query_includes_grade(self):
        self.lesson.ai_payload = {'_brief': {'grade': 4}}
        link = teacher_search_links(self.lesson)[0]
        query = parse_qs(urlparse(link['url']).query)['search_query'][0]
        self.assertIn('الصف 4', query)
        self.assertIn(self.lesson.title, query)

    def test_manual_source_is_pending_and_not_a_fake_ai_result(self):
        url = reverse('open_learning_ai_search', args=[self.lesson.pk])
        fields = {'action': 'add_selected', 'title': 'شرح الفاعل', 'url': 'https://example.com/lesson', 'resource_type': 'video'}
        with patch('open_learning.ai_views.SearchService.search_all') as search:
            self.assertEqual(self.client.post(url, fields).status_code, 302)
            self.client.post(url, fields)
        self.assertEqual(self.lesson.resources.count(), 1)
        resource = self.lesson.resources.get()
        self.assertEqual(resource.status, 'pending')
        self.assertFalse(resource.is_ai_generated)
        self.assertEqual(resource.created_by, self.user)
        search.assert_not_called()

    def test_manual_source_rejects_unsafe_scheme(self):
        response = self.client.post(reverse('open_learning_ai_search', args=[self.lesson.pk]),
            {'action': 'add_selected', 'title': 'مصدر', 'url': 'javascript:alert(1)', 'resource_type': 'link'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['selected_source_form'].errors)
        self.assertEqual(self.lesson.resources.count(), 0)

    def test_student_and_other_teacher_cannot_add_sources(self):
        for role in ('student', 'teacher'):
            with self.subTest(role=role):
                user = User.objects.create_user('source-other-' + role)
                Profile.objects.create(user=user, role=role)
                if role == 'student':
                    Student.objects.create(user=user, student_id='772244', full_name='طالب', student_class=self.grade)
                else:
                    Teacher.objects.create(user=user, full_name='معلم آخر')
                self.client.force_login(user)
                response = self.client.post(reverse('open_learning_ai_search', args=[self.lesson.pk]),
                    {'action': 'add_selected', 'title': 'مصدر', 'url': 'https://example.com/lesson', 'resource_type': 'link'})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self.lesson.resources.count(), 0)
                if role == 'student':
                    response = self.client.get(reverse('open_learning_lesson_detail', args=[self.lesson.pk]))
                    self.assertNotContains(response, 'بحث موجّه في مواقع خارجية')

    def test_catalog_result_is_imported_pending_without_extra_head_requests(self):
        item = {'title': 'الإعراب', 'url': 'https://ar.wikipedia.org/?curid=321', 'snippet': 'الإعراب في العربية',
                'group': 'reading', 'catalog_name': 'ويكيبيديا العربية', 'catalog_reference': True}
        with patch('open_learning.services.open_sources.catalog_search', return_value=[item]), \
             patch('open_learning.services.search_service.SearchService.validate_url') as head, \
             patch.dict(os.environ, {'SEARCH_PROVIDER': 'open_catalog'}):
            response = self.client.post(reverse('open_learning_ai_search', args=[self.lesson.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.lesson.resources.count(), 1)
        self.assertEqual(self.lesson.resources.get().status, 'pending')
        head.assert_not_called()
