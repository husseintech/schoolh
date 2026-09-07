from datetime import date
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from school.models import Class, Profile, Student, UserPermission

from .google_drive import GoogleDriveService
from .models import AIUsageLog, SchoolRadioEntry, SchoolRadioFile
from .services.ai_service import AIServiceUnavailable, MockProvider, validate_radio_program


class SchoolRadioFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('radio-admin', password='pass')
        Profile.objects.create(user=self.admin, role='admin')
        self.grade = Class.objects.create(name='الصف الثاني أ')
        self.student_user = User.objects.create_user('radio-student')
        Profile.objects.create(user=self.student_user, role='student')
        self.student = Student.objects.create(
            user=self.student_user, student_id='991122334', full_name='طالب الإذاعة', student_class=self.grade,
        )
        self.client.force_login(self.admin)

    def create_entry(self, **kwargs):
        values = {
            'event_date': date(2026, 9, 8),
            'title': 'إذاعة القدس الشريف',
            'topic': 'القدس الشريف',
            'category': 'national',
            'created_by': self.admin,
        }
        values.update(kwargs)
        return SchoolRadioEntry.objects.create(**values)

    def grant_radio(self, *actions):
        UserPermission.objects.update_or_create(
            user=self.student_user,
            defaults={'permissions': {'school_radio': list(actions)}},
        )

    def test_admin_can_create_entry_with_presenters_and_participants(self):
        response = self.client.post(reverse('ol_school_radio_add'), {
            'event_date': '2026-09-08',
            'title': 'إذاعة يوم الأسير الفلسطيني',
            'topic': 'يوم الأسير الفلسطيني',
            'category': 'national',
            'presenters': [self.student.pk],
            'participants': [self.student.pk],
            'additional_presenters': 'طالب ضيف',
            'additional_participants': '',
            'notes': 'تجربة الميكروفون قبل الطابور.',
        })
        entry = SchoolRadioEntry.objects.get()
        self.assertRedirects(response, reverse('ol_school_radio_detail', args=[entry.pk]))
        self.assertEqual(entry.created_by, self.admin)
        self.assertEqual(list(entry.presenters.all()), [self.student])
        self.assertEqual(list(entry.participants.all()), [self.student])

    def test_account_without_radio_permission_cannot_view_or_create_records(self):
        self.client.force_login(self.student_user)
        self.assertRedirects(self.client.get(reverse('ol_school_radio_list')), reverse('home'))
        self.assertRedirects(self.client.post(reverse('ol_school_radio_add'), {}), reverse('home'))
        self.assertEqual(SchoolRadioEntry.objects.count(), 0)

    def test_individual_view_permission_shows_navigation_and_allows_read_only_access(self):
        entry = self.create_entry()
        self.grant_radio('view')
        self.client.force_login(self.student_user)

        home = self.client.get(reverse('home'))
        listing = self.client.get(reverse('ol_school_radio_list'))

        self.assertContains(home, reverse('ol_school_radio_list'))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, entry.title)
        self.assertNotContains(listing, reverse('ol_school_radio_add'))
        self.assertEqual(self.client.get(reverse('ol_school_radio_detail', args=[entry.pk])).status_code, 200)
        self.assertRedirects(
            self.client.get(reverse('ol_school_radio_edit', args=[entry.pk])),
            reverse('home'),
        )

    def test_radio_navigation_is_hidden_without_view_permission(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('home'))

        self.assertNotContains(response, reverse('ol_school_radio_list'))

    def test_individual_full_grant_allows_account_to_create_radio_record(self):
        self.grant_radio('view', 'add', 'edit', 'delete', 'generate', 'review')
        self.client.force_login(self.student_user)

        response = self.client.post(reverse('ol_school_radio_add'), {
            'event_date': '2026-09-09',
            'title': 'إذاعة بحساب مفوض',
            'topic': 'العلم',
            'category': 'educational',
            'presenters': [self.student.pk],
            'participants': [],
            'additional_presenters': '',
            'additional_participants': '',
            'notes': '',
        })

        entry = SchoolRadioEntry.objects.get(title='إذاعة بحساب مفوض')
        self.assertRedirects(response, reverse('ol_school_radio_detail', args=[entry.pk]))
        self.assertEqual(entry.created_by, self.student_user)

    def test_radio_actions_are_protected_independently_from_view(self):
        entry = self.create_entry()
        self.grant_radio('view')
        self.client.force_login(self.student_user)

        protected_requests = [
            self.client.post(reverse('ol_school_radio_add_files', args=[entry.pk])),
            self.client.post(reverse('ol_school_radio_generate_word', args=[entry.pk]), {'topic': 'العلم'}),
            self.client.post(reverse('ol_school_radio_approve_ai', args=[entry.pk])),
            self.client.post(reverse('ol_school_radio_delete', args=[entry.pk])),
        ]

        for response in protected_requests:
            self.assertRedirects(response, reverse('home'))
        self.assertTrue(SchoolRadioEntry.objects.filter(pk=entry.pk).exists())

    def test_account_permissions_page_lists_school_radio_actions(self):
        response = self.client.get(reverse('edit_account', args=[self.student_user.pk]))
        section = next(
            item for item in response.context['permission_sections']
            if item['key'] == 'school_radio'
        )

        self.assertEqual(section['label'], 'ملف الإذاعة المدرسية')
        self.assertEqual(
            {action['key'] for action in section['actions']},
            {'view', 'add', 'edit', 'delete', 'generate', 'review'},
        )

    def test_invalid_date_filter_is_ignored(self):
        self.create_entry()
        response = self.client.get(reverse('ol_school_radio_list'), {'date_from': 'not-a-date'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'إذاعة القدس الشريف')

    def test_upload_uses_named_folder_and_date_subfolder(self):
        entry = self.create_entry()
        image = SimpleUploadedFile('camera.jpg', b'jpeg-bytes', content_type='image/jpeg')
        result = {
            'id': 'drive-file-1', 'webViewLink': 'https://drive.google.com/file/d/1/view',
            'mimeType': 'image/jpeg', 'size': '10',
        }
        with patch('open_learning.radio_views.GoogleDriveService.is_connected', return_value=True), \
             patch('open_learning.radio_views.GoogleDriveService.upload_to_folder_path', return_value=result) as upload:
            response = self.client.post(reverse('ol_school_radio_add_files', args=[entry.pk]), {'files': image})
        self.assertRedirects(response, reverse('ol_school_radio_detail', args=[entry.pk]))
        upload.assert_called_once_with(
            'camera.jpg', b'jpeg-bytes', 'image/jpeg', ['ملف الإذاعة المدرسية', '2026-09-08'],
        )
        saved = entry.files.get()
        self.assertEqual(saved.google_drive_file_id, 'drive-file-1')
        self.assertTrue(saved.is_image)

    def test_unsafe_file_type_is_not_uploaded(self):
        entry = self.create_entry()
        bad_file = SimpleUploadedFile('page.html', b'<script>alert(1)</script>', content_type='text/html')
        with patch('open_learning.radio_views.GoogleDriveService.is_connected', return_value=True), \
             patch('open_learning.radio_views.GoogleDriveService.upload_to_folder_path') as upload:
            self.client.post(reverse('ol_school_radio_add_files', args=[entry.pk]), {'files': bad_file})
        upload.assert_not_called()
        self.assertFalse(entry.files.exists())

    def test_radio_file_is_streamed_through_authenticated_view(self):
        entry = self.create_entry()
        radio_file = SchoolRadioFile.objects.create(
            entry=entry, file_name='word.jpg', file_type='image/jpeg', google_drive_file_id='drive-file-2',
        )
        with patch('open_learning.radio_views.GoogleDriveService.download_file', return_value=(b'image', 'image/jpeg', 'word.jpg')):
            response = self.client.get(reverse('ol_school_radio_file_open', args=[radio_file.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'image')
        self.assertEqual(response['Content-Type'], 'image/jpeg')

    def test_word_generation_is_saved_as_pending_draft(self):
        entry = self.create_entry(topic='')
        data, _, _ = MockProvider().generate_radio_word('القدس الشريف')
        provider = Mock(name='gemini', model='gemini-2.5-flash')
        provider.generate_radio_word.return_value = (data, 120, 35)
        with patch('open_learning.radio_views.get_provider', return_value=provider):
            response = self.client.post(
                reverse('ol_school_radio_generate_word', args=[entry.pk]), {'topic': 'القدس الشريف'},
            )
        self.assertRedirects(response, reverse('ol_school_radio_detail', args=[entry.pk]))
        entry.refresh_from_db()
        self.assertEqual(entry.ai_status, 'pending')
        self.assertEqual(entry.ai_word['title'], data['title'])
        self.assertEqual(entry.topic, 'القدس الشريف')
        self.assertTrue(AIUsageLog.objects.filter(operation='radio_word', success=True).exists())

    def test_full_program_requires_review_then_can_be_approved(self):
        entry = self.create_entry()
        data, _, _ = MockProvider().generate_radio_program(entry.topic)
        provider = Mock(name='gemini', model='gemini-2.5-flash')
        provider.generate_radio_program.return_value = (data, 500, 80)
        with patch('open_learning.radio_views.get_provider', return_value=provider):
            self.client.post(reverse('ol_school_radio_generate_program', args=[entry.pk]), {'topic': entry.topic})
        entry.refresh_from_db()
        self.assertEqual(entry.ai_status, 'pending')
        self.assertEqual(len(entry.ai_program['quran']['verses']), 7)
        self.client.post(reverse('ol_school_radio_approve_ai', args=[entry.pk]))
        entry.refresh_from_db()
        self.assertEqual(entry.ai_status, 'approved')
        self.assertEqual(entry.ai_reviewed_by, self.admin)

    def test_ai_failure_preserves_previous_content(self):
        entry = self.create_entry(ai_word={'title': 'قديم', 'paragraphs': ['أ' * 90, 'ب' * 90]})
        provider = Mock(name='gemini', model='gemini-2.5-flash')
        provider.generate_radio_word.side_effect = AIServiceUnavailable('تعذر التوليد')
        with patch('open_learning.radio_views.get_provider', return_value=provider):
            self.client.post(reverse('ol_school_radio_generate_word', args=[entry.pk]), {'topic': entry.topic})
        entry.refresh_from_db()
        self.assertEqual(entry.ai_word['title'], 'قديم')
        self.assertTrue(AIUsageLog.objects.filter(operation='radio_word', success=False).exists())


class SchoolRadioServiceTests(SimpleTestCase):
    def test_nested_drive_folder_uses_configured_order(self):
        service = GoogleDriveService()
        service.root_folder_id = 'root-id'
        with patch.object(service, '_build_folder', side_effect=['radio-id', 'date-id']) as build:
            self.assertEqual(service.ensure_folder_path(['ملف الإذاعة المدرسية', '2026-09-08']), 'date-id')
        self.assertEqual(build.call_args_list[0].args, ('ملف الإذاعة المدرسية', 'root-id'))
        self.assertEqual(build.call_args_list[1].args, ('2026-09-08', 'radio-id'))

    def test_program_validation_rejects_less_than_seven_verses(self):
        data, _, _ = MockProvider().generate_radio_program('العلم')
        data['quran']['verses'] = data['quran']['verses'][:6]
        data['quran']['end_verse'] = 6
        with self.assertRaises(AIServiceUnavailable):
            validate_radio_program(data)
