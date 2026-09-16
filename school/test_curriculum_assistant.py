import gzip
import json
from pathlib import Path
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from school.curriculum_assistant import (
    answer_cache_key,
    curriculum_video_resource,
    extract_youtube_video_id,
    import_curriculum_package,
    retrieve_curriculum_context,
)
from school.views import get_clearable_tables
from school.models import (
    Class,
    CurriculumAnswerCache,
    CurriculumAssistantSettings,
    CurriculumConversation,
    CurriculumLesson,
    CurriculumLessonVideo,
    CurriculumMessage,
    CurriculumPage,
    CurriculumSource,
    Profile,
    Student,
    Subject,
    Teacher,
    UserPermission,
)


class CurriculumAssistantTests(TestCase):
    def setUp(self):
        self.grade_four = Class.objects.create(name='الصف الرابع أ')
        self.grade_five = Class.objects.create(name='5 أ')
        self.student_user = User.objects.create_user(username='grade4-student', password='pass')
        Profile.objects.create(user=self.student_user, role='student')
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='curr-4001',
            full_name='سلمى أحمد محمود',
            student_class=self.grade_four,
        )
        self.other_user = User.objects.create_user(username='grade5-student', password='pass')
        Profile.objects.create(user=self.other_user, role='student')
        Student.objects.create(
            user=self.other_user,
            student_id='curr-5001',
            full_name='رامي خالد علي',
            student_class=self.grade_five,
        )
        self.admin = User.objects.create_user(username='curr-admin', password='pass')
        Profile.objects.create(user=self.admin, role='admin')
        self.teacher = User.objects.create_user(username='curr-teacher', password='pass')
        Profile.objects.create(user=self.teacher, role='teacher')
        self.science_subject = Subject.objects.create(name='العلوم')
        self.teacher_record = Teacher.objects.create(user=self.teacher, full_name='معلمة العلوم')
        self.teacher_record.classes.add(self.grade_four)
        self.teacher_record.subjects.add(self.science_subject)
        self.source = CurriculumSource.objects.create(
            grade_level=4,
            term=1,
            subject_code='science',
            subject_name='العلوم والحياة',
            title='العلوم للصف الرابع - الجزء الأول',
            original_filename='science.pdf',
            source_sha256='1' * 64,
            page_count=3,
            status='published',
            created_by=self.admin,
        )
        self.lesson = CurriculumLesson.objects.create(
            source=self.source,
            unit_title='أجهزة جسم الإنسان',
            unit_order=1,
            lesson_order=1,
            title='الغذاء المتوازن',
            start_printed_page=9,
            end_printed_page=11,
            start_pdf_page=1,
            end_pdf_page=3,
        )
        self.video = CurriculumLessonVideo.objects.create(
            lesson=self.lesson,
            title='شرح الغذاء المتوازن',
            youtube_video_id='AbCdEfGhI12',
            added_by=self.admin,
        )
        self.page = CurriculumPage.objects.create(
            source=self.source,
            lesson=self.lesson,
            pdf_page_number=1,
            printed_page_number=9,
            text='الغذاء المتوازن يحتوي مجموعات غذائية متنوعة وبكميات مناسبة.',
            normalized_text='الغذاء المتوازن يحتوي مجموعات غذاييه متنوعه وبكميات مناسبه',
        )
        CurriculumPage.objects.create(
            source=self.source,
            lesson=self.lesson,
            pdf_page_number=2,
            printed_page_number=10,
            text='يعرض الهرم الغذائي مجموعات الغذاء التي يحتاج إليها الجسم.',
            normalized_text='يعرض الهرم الغذايي مجموعات الغذاء التي يحتاج اليها الجسم',
        )
        CurriculumPage.objects.create(
            source=self.source,
            lesson=self.lesson,
            pdf_page_number=3,
            printed_page_number=11,
            text='',
            normalized_text='',
            needs_visual_review=True,
        )

    def ask(self, payload):
        return self.client.post(
            reverse('curriculum_assistant_ask'),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_grade_four_student_sees_published_sources_and_dedicated_page(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('curriculum_assistant'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'مساعد المنهاج')
        self.assertContains(response, self.source.subject_name)
        self.assertContains(response, self.lesson.title)
        self.assertContains(response, 'إجابات موثقة')

    def test_other_grades_do_not_receive_grade_four_sources(self):
        self.client.force_login(self.other_user)
        page = self.client.get(reverse('curriculum_assistant'))
        self.assertContains(page, 'النسخة الأولى مخصصة للصف الرابع')
        denied = self.ask({
            'question': 'اشرح الغذاء المتوازن',
            'source_id': self.source.pk,
            'lesson_id': self.lesson.pk,
        })
        self.assertEqual(denied.status_code, 403)

    def test_teacher_cannot_use_student_curriculum_assistant(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('curriculum_assistant'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_retrieval_is_limited_to_selected_source_and_lesson(self):
        contexts = retrieve_curriculum_context(self.source, self.lesson, 'ما الغذاء المتوازن؟')
        self.assertTrue(contexts)
        self.assertTrue(all(item['page_id'] in set(self.lesson.pages.values_list('pk', flat=True)) for item in contexts))
        self.assertIn('الغذاء المتوازن', contexts[0]['text'])

    def test_ai_receives_no_student_identity_and_returns_page_citation(self):
        provider = Mock()

        def answer(**kwargs):
            return ({
                'answerable': True,
                'answer': 'الغذاء المتوازن يجمع مجموعات غذائية متنوعة بكميات مناسبة.',
                'citations': [kwargs['page_contexts'][0]['id']],
                'suggestions': ['ما الهرم الغذائي؟'],
            }, 90, 35)

        provider.answer_curriculum_question.side_effect = answer
        self.client.force_login(self.student_user)
        with patch('school.curriculum_assistant_views.get_provider', return_value=provider):
            response = self.ask({
                'question': 'ما الغذاء المتوازن؟',
                'source_id': self.source.pk,
                'lesson_id': self.lesson.pk,
            })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['citations'][0]['printed_page'], 9)
        self.assertEqual(payload['citations'][0]['url'], reverse('curriculum_source_page', args=[self.page.pk]))
        self.assertEqual(payload['video']['count'], 1)
        self.assertEqual(payload['video']['items'][0]['title'], self.video.title)
        self.assertIn('youtube-nocookie.com/embed/AbCdEfGhI12', payload['video']['items'][0]['embed_url'])
        kwargs = provider.answer_curriculum_question.call_args.kwargs
        self.assertNotIn('student', kwargs)
        self.assertNotIn('سلمى', json.dumps(kwargs, ensure_ascii=False))
        assistant_message = CurriculumMessage.objects.get(role='assistant')
        self.assertEqual(assistant_message.estimated_tokens, 90)
        self.assertEqual(assistant_message.citations, [{'page_id': self.page.pk}])

    def test_unapproved_citation_never_returns_copied_source_fallback(self):
        provider = Mock()
        provider.answer_curriculum_question.return_value = ({
            'answerable': True,
            'answer': 'إجابة بلا مرجع صالح',
            'citations': ['P999999'],
            'suggestions': [],
        }, 1, 1)
        self.client.force_login(self.student_user)
        with patch('school.curriculum_assistant_views.get_provider', return_value=provider):
            response = self.ask({
                'question': 'اشرح الفكرة الموجودة',
                'source_id': self.source.pk,
                'lesson_id': self.lesson.pk,
            })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'ai_temporarily_unavailable')
        self.assertIn('لم نعرض نصًا منسوخًا', response.json()['error'])
        self.assertFalse(CurriculumMessage.objects.filter(role='assistant').exists())

    def test_provider_failure_returns_retryable_error_without_copying_book(self):
        provider = Mock()
        provider.answer_curriculum_question.side_effect = RuntimeError('provider failed')
        self.client.force_login(self.student_user)
        with patch('school.curriculum_assistant_views.get_provider', return_value=provider):
            response = self.ask({
                'question': 'اشرح لي هذا الدرس خطوة خطوة',
                'source_id': self.source.pk,
                'lesson_id': self.lesson.pk,
            })
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload['code'], 'ai_temporarily_unavailable')
        self.assertTrue(payload['retryable'])
        self.assertFalse(CurriculumMessage.objects.filter(role='assistant').exists())

    def test_exact_answer_cache_avoids_second_ai_call(self):
        CurriculumAnswerCache.objects.create(
            source=self.source,
            lesson=self.lesson,
            normalized_question=answer_cache_key('ما الغذاء المتوازن؟'),
            answer='إجابة محفوظة من الكتاب.',
            citations=[{'page_id': self.page.pk}],
            suggestions=['سؤال آخر'],
        )
        self.client.force_login(self.student_user)
        with patch('school.curriculum_assistant_views.get_provider') as provider:
            response = self.ask({
                'question': 'ما الغذاء المتوازن؟',
                'source_id': self.source.pk,
                'lesson_id': self.lesson.pk,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mode'], 'cache')
        self.assertEqual(response.json()['answer'], 'إجابة محفوظة من الكتاب.')
        provider.assert_not_called()

    def test_lesson_video_library_contains_only_approved_safe_embeds(self):
        video = curriculum_video_resource(self.source, self.lesson)
        self.assertEqual(video['label'], 'فيديوهات الدرس (1)')
        self.assertEqual(video['count'], 1)
        self.assertTrue(video['items'][0]['embed_url'].startswith('https://www.youtube-nocookie.com/embed/'))
        self.assertIsNone(curriculum_video_resource(self.source, None))

    def test_youtube_url_parser_accepts_known_formats_and_rejects_other_hosts(self):
        self.assertEqual(extract_youtube_video_id('https://youtu.be/AbCdEfGhI12'), 'AbCdEfGhI12')
        self.assertEqual(
            extract_youtube_video_id('https://www.youtube.com/watch?v=AbCdEfGhI12&t=4'),
            'AbCdEfGhI12',
        )
        self.assertEqual(extract_youtube_video_id('https://youtube.com/shorts/AbCdEfGhI12'), 'AbCdEfGhI12')
        self.assertEqual(extract_youtube_video_id('https://example.com/watch?v=AbCdEfGhI12'), '')
        self.assertEqual(extract_youtube_video_id('<iframe src="https://youtube.com"></iframe>'), '')

    def test_selected_lesson_page_displays_approved_video_count(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('curriculum_assistant'), {
            'source': self.source.pk,
            'lesson': self.lesson.pk,
        })
        self.assertContains(response, 'فيديوهات الدرس')
        self.assertContains(response, 'curriculumVideoModal')
        self.assertContains(response, self.video.youtube_video_id)

    def test_admin_adds_and_removes_approved_lesson_video(self):
        self.client.force_login(self.admin)
        added = self.client.post(reverse('curriculum_assistant_admin'), {
            'action': 'add_video',
            'lesson_id': self.lesson.pk,
            'video_title': 'شرح الهرم الغذائي',
            'video_url': 'https://www.youtube.com/watch?v=ZyXwVuTsRq0',
        })
        self.assertRedirects(added, reverse('curriculum_assistant_admin'))
        created = CurriculumLessonVideo.objects.get(youtube_video_id='ZyXwVuTsRq0')
        self.assertEqual(created.lesson, self.lesson)
        removed = self.client.post(reverse('curriculum_assistant_admin'), {
            'action': 'delete_video',
            'video_id': created.pk,
        })
        self.assertRedirects(removed, reverse('curriculum_assistant_admin'))
        self.assertFalse(CurriculumLessonVideo.objects.filter(pk=created.pk).exists())

    def test_admin_rejects_non_youtube_video_url(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('curriculum_assistant_admin'), {
            'action': 'add_video',
            'lesson_id': self.lesson.pk,
            'video_title': 'رابط غير موثوق',
            'video_url': 'https://example.com/watch?v=ZyXwVuTsRq0',
        }, follow=True)
        self.assertContains(response, 'رابط الفيديو غير صالح')
        self.assertFalse(CurriculumLessonVideo.objects.filter(title='رابط غير موثوق').exists())

    def test_teacher_manager_is_limited_to_assigned_grade_and_subject(self):
        math_source = CurriculumSource.objects.create(
            grade_level=4, term=1, subject_code='math', subject_name='الرياضيات',
            title='رياضيات الصف الرابع', original_filename='math.pdf', source_sha256='4' * 64,
            page_count=1, status='published', created_by=self.admin,
        )
        math_lesson = CurriculumLesson.objects.create(
            source=math_source, unit_title='الأعداد', unit_order=1, lesson_order=1,
            title='الأعداد الكبيرة', start_pdf_page=1, end_pdf_page=1,
        )
        self.client.force_login(self.teacher)
        page = self.client.get(reverse('curriculum_assistant_manage'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'إدارة مساعد المنهاج')
        self.assertContains(page, self.lesson.title)
        self.assertNotContains(page, math_lesson.title)
        self.assertContains(page, reverse('curriculum_assistant_manage'))

        added = self.client.post(reverse('curriculum_assistant_manage'), {
            'action': 'add_video',
            'lesson_id': self.lesson.pk,
            'video_title': 'شرح أضافته المعلمة',
            'video_url': 'https://youtu.be/ZyXwVuTsRq0',
        })
        self.assertRedirects(added, reverse('curriculum_assistant_manage'))
        created = CurriculumLessonVideo.objects.get(youtube_video_id='ZyXwVuTsRq0')
        self.assertEqual(created.added_by, self.teacher)

        denied = self.client.post(reverse('curriculum_assistant_manage'), {
            'action': 'add_video',
            'lesson_id': math_lesson.pk,
            'video_title': 'فيديو خارج النطاق',
            'video_url': 'https://youtu.be/QwErTyUiOp1',
        })
        self.assertEqual(denied.status_code, 404)
        self.assertFalse(CurriculumLessonVideo.objects.filter(youtube_video_id='QwErTyUiOp1').exists())

        removed = self.client.post(reverse('curriculum_assistant_manage'), {
            'action': 'delete_video', 'video_id': created.pk,
        })
        self.assertRedirects(removed, reverse('curriculum_assistant_manage'))
        self.assertFalse(CurriculumLessonVideo.objects.filter(pk=created.pk).exists())

    def test_teacher_stats_show_only_students_and_successful_answer_counts_in_scope(self):
        conversation = CurriculumConversation.objects.create(
            student=self.student, source=self.source, lesson=self.lesson, title='سؤال خاص',
        )
        CurriculumMessage.objects.create(conversation=conversation, role='user', content='نص سؤال خاص')
        CurriculumMessage.objects.create(conversation=conversation, role='assistant', content='الإجابة الأولى')
        CurriculumMessage.objects.create(conversation=conversation, role='assistant', content='الإجابة الثانية')
        other_student = Student.objects.get(user=self.other_user)
        other_conversation = CurriculumConversation.objects.create(
            student=other_student, source=self.source, lesson=self.lesson, title='خارج الصف',
        )
        CurriculumMessage.objects.create(
            conversation=other_conversation, role='assistant', content='إجابة خارج نطاق المعلم',
        )

        self.client.force_login(self.teacher)
        response = self.client.get(reverse('curriculum_assistant_manage'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['students_with_answers'], 1)
        self.assertEqual(response.context['answered_questions'], 2)
        self.assertEqual(response.context['student_stats'][0]['conversation__student__full_name'], self.student.full_name)
        self.assertEqual(response.context['student_stats'][0]['question_count'], 2)
        self.assertContains(response, self.student.full_name)
        self.assertNotContains(response, other_student.full_name)
        self.assertNotContains(response, 'نص سؤال خاص')
        self.assertNotContains(response, 'الإجابة الأولى')

    def test_teacher_curriculum_manager_permission_can_be_removed(self):
        UserPermission.objects.create(
            user=self.teacher,
            permissions={'curriculum_assistant': []},
        )
        self.client.force_login(self.teacher)
        denied = self.client.get(reverse('curriculum_assistant_manage'))
        self.assertRedirects(denied, reverse('dashboard'))

    def test_teacher_without_add_permission_cannot_add_video(self):
        UserPermission.objects.create(
            user=self.teacher,
            permissions={'curriculum_assistant': ['view', 'monitor']},
        )
        self.client.force_login(self.teacher)
        response = self.client.post(reverse('curriculum_assistant_manage'), {
            'action': 'add_video',
            'lesson_id': self.lesson.pk,
            'video_title': 'غير مسموح',
            'video_url': 'https://youtu.be/ZyXwVuTsRq0',
        }, follow=True)
        self.assertContains(response, 'ليس لديك صلاحية إضافة فيديوهات الدروس')
        self.assertFalse(CurriculumLessonVideo.objects.filter(youtube_video_id='ZyXwVuTsRq0').exists())

    def test_daily_limit_counts_curriculum_answers(self):
        CurriculumAssistantSettings.objects.create(daily_question_limit=1)
        conversation = CurriculumConversation.objects.create(
            student=self.student, source=self.source, lesson=self.lesson, title='سابق',
        )
        CurriculumMessage.objects.create(conversation=conversation, role='assistant', content='إجابة سابقة')
        self.client.force_login(self.student_user)
        response = self.ask({
            'question': 'اشرح لي الهرم الغذائي',
            'source_id': self.source.pk,
            'lesson_id': self.lesson.pk,
        })
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['remaining'], 0)

    def test_privacy_guard_does_not_store_identifier(self):
        self.client.force_login(self.student_user)
        with patch('school.curriculum_assistant_views.get_provider') as provider:
            response = self.ask({
                'question': 'رقم هويتي هو 123456789 هل تحفظه؟',
                'source_id': self.source.pk,
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn('حرصًا على خصوصيتك', response.json()['answer'])
        self.assertFalse(CurriculumConversation.objects.exists())
        provider.assert_not_called()

    def test_students_open_only_published_grade_four_citation_pages(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('curriculum_source_page', args=[self.page.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'صفحة الكتاب 9')
        self.source.status = 'archived'
        self.source.save(update_fields=['status'])
        denied = self.client.get(reverse('curriculum_source_page', args=[self.page.pk]))
        self.assertRedirects(denied, reverse('dashboard'))

    def test_admin_imports_valid_package_as_draft_and_teacher_is_denied(self):
        package = {
            'schema_version': 1,
            'source': {
                'grade_level': 4,
                'term': 1,
                'subject_code': 'math',
                'subject_name': 'الرياضيات',
                'title': 'رياضيات الصف الرابع',
                'edition': 'الجزء الأول',
                'original_filename': 'math.pdf',
                'sha256': '2' * 64,
                'page_count': 2,
            },
            'lessons': [{
                'unit_title': 'الأعداد الكبيرة',
                'unit_order': 1,
                'lesson_order': 1,
                'title': 'الأعداد الكبيرة',
                'start_printed_page': 5,
                'end_printed_page': 6,
                'start_pdf_page': 1,
                'end_pdf_page': 2,
            }],
            'pages': [
                {'pdf_page_number': 1, 'printed_page_number': 5, 'text': 'العدد مليون', 'needs_visual_review': False},
                {'pdf_page_number': 2, 'printed_page_number': 6, 'text': 'القيمة المنزلية', 'needs_visual_review': False},
            ],
        }
        uploaded = SimpleUploadedFile(
            'math.json.gz', gzip.compress(json.dumps(package, ensure_ascii=False).encode()),
            content_type='application/gzip',
        )
        source, created = import_curriculum_package(uploaded, self.admin)
        self.assertTrue(created)
        self.assertEqual(source.status, 'draft')
        self.assertEqual(source.pages.count(), 2)
        self.assertEqual(source.lessons.count(), 1)

        self.client.force_login(self.teacher)
        denied = self.client.get(reverse('curriculum_assistant_admin'))
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(denied.url, reverse('dashboard'))

    def test_admin_publication_archives_previous_subject_version(self):
        draft = CurriculumSource.objects.create(
            grade_level=4, term=1, subject_code='science', subject_name='العلوم والحياة',
            title='إصدار أحدث', original_filename='new.pdf', source_sha256='3' * 64,
            page_count=1, status='draft', created_by=self.admin,
        )
        lesson = CurriculumLesson.objects.create(
            source=draft, unit_title='وحدة', unit_order=1, lesson_order=1, title='درس',
            start_pdf_page=1, end_pdf_page=1,
        )
        CurriculumPage.objects.create(
            source=draft, lesson=lesson, pdf_page_number=1, text='صفحة مكتملة', normalized_text='صفحه مكتمله',
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse('curriculum_assistant_admin'), {
            'action': 'publish', 'source_id': draft.pk,
        })
        self.assertRedirects(response, reverse('curriculum_assistant_admin'))
        self.source.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(self.source.status, 'archived')
        self.assertEqual(draft.status, 'published')

    def test_frontend_assets_exist(self):
        self.assertTrue(finders.find('school/css/curriculum_assistant.css'))
        self.assertTrue(finders.find('school/css/curriculum_manager.css'))
        assistant_js = finders.find('school/js/curriculum_assistant.js')
        self.assertTrue(assistant_js)
        javascript = Path(assistant_js).read_text(encoding='utf-8')
        self.assertIn('speechSynthesis', javascript)
        self.assertIn('chat-video', javascript)
        self.assertIn('youtube-nocookie.com/embed/', javascript)
        self.assertTrue(finders.find('school/js/curriculum_source_admin.js'))

    def test_conversations_are_registered_for_year_start_maintenance(self):
        keys = {row[0] for row in get_clearable_tables()}
        self.assertIn('curriculum_conversations', keys)

    def test_pdf_upload_rejects_file_that_does_not_match_indexed_source(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('curriculum_pdf_upload_start', args=[self.source.pk]),
            data=json.dumps({
                'name': 'science.pdf',
                'type': 'application/pdf',
                'size': 1024,
                'sha256': 'f' * 64,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'source_hash_mismatch')
