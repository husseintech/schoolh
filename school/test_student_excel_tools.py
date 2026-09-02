from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from school.models import Class, Profile, Student


def excel_upload(rows, name='students.xlsx'):
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    content = BytesIO()
    workbook.save(content)
    workbook.close()
    return SimpleUploadedFile(
        name,
        content.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


class StudentExcelToolsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin-test', password='safe-password')
        Profile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

        self.existing_class = Class.objects.create(name='1أ')
        self.existing_user = User.objects.create_user(username='123456789', password='original-pass')
        Profile.objects.create(user=self.existing_user, role='student')
        self.existing_student = Student.objects.create(
            user=self.existing_user,
            student_id='123456789',
            full_name='طالب موجود',
            student_class=self.existing_class,
            parent_name='ولي أمر موجود',
            plain_password='original-pass',
        )

    def test_student_page_shows_separate_import_and_identity_check_actions(self):
        response = self.client.get(reverse('student_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'استيراد طلاب')
        self.assertContains(response, 'فحص الطلاب غير الموجودين')
        self.assertContains(response, reverse('check_missing_student_ids'))

    def test_identity_check_lists_only_missing_ids_and_writes_nothing(self):
        before_students = Student.objects.count()
        before_users = User.objects.count()
        upload = excel_upload([
            ['تقرير الطلاب في الصفوف', None, None],
            [None, None, None],
            ['رقم', 'اسم الطالب', 'رقم هوية الطالب'],
            [1, 'طالب موجود', 123456789],
            [2, 'طالب جديد', 987654321],
            [3, 'مكرر', 987654321],
            [4, 'قيمة غير صالحة', 'ABC-12'],
        ])

        response = self.client.post(reverse('check_missing_student_ids'), {'excel_file': upload})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['missing_ids'], ['987654321'])
        self.assertEqual(response.context['existing_count'], 1)
        self.assertEqual(response.context['duplicate_count'], 1)
        self.assertEqual(response.context['invalid_count'], 1)
        self.assertEqual(Student.objects.count(), before_students)
        self.assertEqual(User.objects.count(), before_users)

    def test_identity_check_accepts_a_single_column_without_header(self):
        upload = excel_upload([['123456789'], ['٩٨٧٦٥٤٣٢١']])

        response = self.client.post(reverse('check_missing_student_ids'), {'excel_file': upload})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['missing_ids'], ['987654321'])
        self.assertEqual(response.context['existing_count'], 1)

    def test_full_import_skips_existing_student_without_modifying_it(self):
        upload = excel_upload([
            ['الاسم الكامل', 'رقم الهوية', 'الصف', 'هاتف ولي الأمر', 'اسم ولي الأمر', 'العنوان', 'تاريخ الميلاد', 'كلمة المرور', 'اسم المستخدم'],
            ['اسم يجب ألا يستبدل', 123456789, '2ب', '', 'ولي جديد', '', None, 'new-pass', 'new-username'],
            ['طالب جديد', 987654321, '2ب', '', '', '', None, '', ''],
        ])

        response = self.client.post(reverse('import_students'), {'excel_file': upload})

        self.assertRedirects(response, reverse('student_list'))
        self.existing_student.refresh_from_db()
        self.existing_user.refresh_from_db()
        self.assertEqual(self.existing_student.full_name, 'طالب موجود')
        self.assertEqual(self.existing_student.student_class, self.existing_class)
        self.assertEqual(self.existing_student.plain_password, 'original-pass')
        self.assertTrue(self.existing_user.check_password('original-pass'))

        added = Student.objects.get(student_id='987654321')
        self.assertEqual(added.full_name, 'طالب جديد')
        self.assertEqual(added.student_class.name, '2ب')
        self.assertEqual(added.user.username, '987654321')

    def test_non_admin_cannot_run_identity_check(self):
        teacher_user = User.objects.create_user(username='teacher-test', password='safe-password')
        Profile.objects.create(user=teacher_user, role='teacher')
        self.client.force_login(teacher_user)

        response = self.client.post(
            reverse('check_missing_student_ids'),
            {'excel_file': excel_upload([['رقم الهوية'], ['987654321']])},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
