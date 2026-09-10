from datetime import date

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from school.attendance_register import (
    build_school_year_months,
    build_student_rows,
    normalize_row_count,
)
from school.models import Class, Profile, SchoolInfo, Student, Teacher


class AttendanceRegisterCalendarTests(SimpleTestCase):
    def test_school_year_has_august_through_june_in_correct_order(self):
        months = build_school_year_months(2026)

        self.assertEqual([month['number'] for month in months], [8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6])
        self.assertEqual([month['year'] for month in months], [2026] * 5 + [2027] * 6)
        self.assertEqual([month['semester'] for month in months], ['الأول'] * 6 + ['الثاني'] * 5)

    def test_august_2026_is_fully_shaded_but_future_august_is_ready_for_use(self):
        august_2026 = build_school_year_months(2026)[0]
        august_2027 = build_school_year_months(2027)[0]

        self.assertTrue(all(day['shaded'] for day in august_2026['days'] if day['exists']))
        self.assertTrue(any(not day['shaded'] for day in august_2027['days'] if day['exists']))

    def test_weekends_and_only_named_official_holidays_are_shaded(self):
        months = build_school_year_months(2026)
        december = next(month for month in months if month['number'] == 12)
        january = next(month for month in months if month['number'] == 1)

        self.assertTrue(december['days'][24]['shaded'])
        self.assertEqual(december['days'][24]['holiday_name'], 'عيد الميلاد المجيد')
        self.assertTrue(january['days'][0]['shaded'])
        self.assertTrue(january['days'][6]['shaded'])
        for month in months[1:]:
            for day in month['days']:
                if not day['exists']:
                    self.assertFalse(day['shaded'])
                    continue
                weekday = date(month['year'], month['number'], day['number']).weekday()
                should_be_shaded = weekday in (4, 5) or (month['number'], day['number']) in {
                    (12, 25), (1, 1), (1, 7),
                }
                self.assertEqual(day['shaded'], should_be_shaded)

    def test_february_length_handles_regular_and_leap_years(self):
        february_2027 = next(month for month in build_school_year_months(2026) if month['number'] == 2)
        february_2028 = next(month for month in build_school_year_months(2027) if month['number'] == 2)

        self.assertEqual(february_2027['days_in_month'], 28)
        self.assertEqual(february_2028['days_in_month'], 29)
        self.assertFalse(february_2027['days'][28]['exists'])
        self.assertTrue(february_2028['days'][28]['exists'])

    def test_student_rows_always_keep_47_numbered_lines(self):
        class StudentStub:
            def __init__(self, full_name):
                self.full_name = full_name

        rows = build_student_rows([StudentStub('الطالب الأول'), StudentStub('الطالب الثاني')])

        self.assertEqual(len(rows), 47)
        self.assertEqual(rows[0], {'number': 1, 'name': 'الطالب الأول'})
        self.assertEqual(rows[-1], {'number': 47, 'name': ''})

    def test_row_count_can_be_selected_only_between_35_and_50(self):
        self.assertEqual(normalize_row_count(35), 35)
        self.assertEqual(normalize_row_count('50'), 50)
        self.assertEqual(normalize_row_count(34), 47)
        self.assertEqual(normalize_row_count(51), 47)
        self.assertEqual(normalize_row_count('invalid'), 47)

    def test_student_rows_follow_the_selected_manual_count(self):
        self.assertEqual(len(build_student_rows([], 35)), 35)
        self.assertEqual(len(build_student_rows([], 50)), 50)

    def test_august_full_shading_can_be_disabled_without_removing_weekends(self):
        august = build_school_year_months(2026, shade_august_fully=False)[0]

        self.assertFalse(august['shade_all'])
        for day in august['days']:
            weekday = date(2026, 8, day['number']).weekday()
            self.assertEqual(day['shaded'], weekday in (4, 5))


class AttendanceRegisterAccessTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='register-admin', password='safe-password')
        Profile.objects.create(user=self.admin_user, role='admin')

        self.guardian_user = User.objects.create_user(username='register-guardian', password='safe-password')
        Profile.objects.create(user=self.guardian_user, role='teacher')
        self.guardian = Teacher.objects.create(user=self.guardian_user, full_name='سامي مربي الصف')
        self.guardian_class = Class.objects.create(name='السادس ب', guardian=self.guardian)

        self.other_user = User.objects.create_user(username='register-other', password='safe-password')
        Profile.objects.create(user=self.other_user, role='teacher')
        self.other_teacher = Teacher.objects.create(user=self.other_user, full_name='معلم دون تربية صف')

        self.student_user_one = User.objects.create_user(username='register-student-1', password='safe-password')
        Profile.objects.create(user=self.student_user_one, role='student')
        Student.objects.create(
            user=self.student_user_one,
            student_id='440001',
            full_name='ياسر الطالب',
            student_class=self.guardian_class,
        )
        self.student_user_two = User.objects.create_user(username='register-student-2', password='safe-password')
        Profile.objects.create(user=self.student_user_two, role='student')
        Student.objects.create(
            user=self.student_user_two,
            student_id='440002',
            full_name='أحمد الطالب',
            student_class=self.guardian_class,
        )
        SchoolInfo.objects.create(
            name_ar='ذكور المنصور الأساسية',
            name_en='Al Mansour Basic School',
            principal_name='حسين حمامدة',
            national_number='12345',
        )

    def test_admin_selects_only_a_teacher_who_is_a_class_guardian(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('attendance_register'), {'teacher': self.guardian.id, 'year': 2026})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_teacher'], self.guardian)
        self.assertEqual(response.context['guardian_class'], self.guardian_class)
        self.assertContains(response, 'سامي مربي الصف — السادس ب')
        self.assertNotContains(response, 'معلم دون تربية صف')
        self.assertContains(response, 'طباعة الغلاف')
        self.assertContains(response, 'طباعة الدفتر')

    def test_invalid_teacher_parameter_does_not_cause_a_server_error(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('attendance_register'), {'teacher': 'not-a-number'})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['selected_teacher'])

    def test_homeroom_teacher_sees_the_menu_and_only_their_own_register(self):
        self.client.force_login(self.guardian_user)

        dashboard = self.client.get(reverse('dashboard'))
        response = self.client.get(reverse('attendance_register'), {'teacher': self.other_teacher.id, 'year': 2026})

        self.assertContains(dashboard, 'دفتر الحضور والغياب')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_teacher'], self.guardian)
        self.assertEqual(response.context['guardian_class'], self.guardian_class)

    def test_non_homeroom_teacher_cannot_see_or_open_the_register(self):
        self.client.force_login(self.other_user)

        dashboard = self.client.get(reverse('dashboard'))
        response = self.client.get(reverse('attendance_register'))
        print_response = self.client.get(reverse('attendance_register_print'), {'teacher': self.guardian.id})

        self.assertNotContains(dashboard, 'دفتر الحضور والغياب')
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(print_response.status_code, 302)
        self.assertEqual(print_response.url, reverse('attendance_register'))

    def test_student_account_cannot_open_register_urls(self):
        self.client.force_login(self.student_user_one)

        for url_name in ('attendance_register', 'attendance_register_cover', 'attendance_register_print'):
            response = self.client.get(reverse(url_name), {'teacher': self.guardian.id})
            self.assertRedirects(response, reverse('dashboard'))

    def test_print_book_has_14_pages_11_months_and_47_sorted_student_rows(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('attendance_register_print'), {'teacher': self.guardian.id, 'year': 2026})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['months']), 11)
        self.assertEqual(len(response.context['student_rows']), 47)
        self.assertEqual(response.context['student_rows'][0]['name'], 'أحمد الطالب')
        self.assertEqual(response.context['student_rows'][1]['name'], 'ياسر الطالب')
        self.assertContains(response, 'data-page-kind="attendance-month"', count=11)
        self.assertEqual(response.content.count(b'<section class="register-page'), 14)
        self.assertContains(response, 'من الدوام الكلي<br>........')
        self.assertNotContains(response, '190')
        self.assertNotContains(response, 'WWWW')
        self.assertNotContains(response, '###')
        self.assertNotContains(response, 'أحمد محمود الزعارير')

    def test_cover_is_separate_and_uses_live_school_data(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('attendance_register_cover'), {'teacher': self.guardian.id, 'year': 2026})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ذكور المنصور الأساسية')
        self.assertContains(response, 'سامي مربي الصف')
        self.assertContains(response, 'السادس ب')
        self.assertContains(response, '2026/2027')
        self.assertContains(response, 'حسين حمامدة')
        self.assertEqual(response.content.count(b'data-page-kind="cover"'), 1)

    def test_admin_can_choose_35_rows_and_disable_full_august_shading(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('attendance_register_print'), {
            'teacher': self.guardian.id,
            'year': 2026,
            'rows': 35,
            'shade_august': 0,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['row_count'], 35)
        self.assertEqual(len(response.context['student_rows']), 35)
        self.assertFalse(response.context['shade_august'])
        august = response.context['months'][0]
        self.assertTrue(any(day['shaded'] for day in august['days']))
        self.assertTrue(any(not day['shaded'] for day in august['days']))
        self.assertContains(response, '--status-row-height:7.286mm')
        self.assertContains(response, '--attendance-row-height:6.514mm')
        self.assertNotContains(response, 'august-column')

    def test_teacher_can_choose_50_rows_and_enable_full_august_shading(self):
        self.client.force_login(self.guardian_user)

        response = self.client.get(reverse('attendance_register_print'), {
            'teacher': self.other_teacher.id,
            'year': 2026,
            'rows': 50,
            'shade_august': 1,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_teacher'], self.guardian)
        self.assertEqual(response.context['row_count'], 50)
        self.assertTrue(response.context['shade_august'])
        self.assertTrue(all(day['shaded'] for day in response.context['months'][0]['days']))
