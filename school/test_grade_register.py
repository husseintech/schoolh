from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from school.grade_register import (
    BOOK_TYPE_STAGE,
    BOOK_TYPE_UPPER,
    build_grade_student_rows,
    class_grade,
    grade_book_type,
    grade_label,
    normalize_book_type,
    normalize_grade_row_count,
)
from school.models import Class, Profile, SchoolInfo, Student, Subject, Teacher, TeacherScheduleEntry


class GradeRegisterHelperTests(SimpleTestCase):
    def test_class_grade_handles_numeric_arabic_digit_and_word_labels(self):
        self.assertEqual(class_grade('1أ'), 1)
        self.assertEqual(class_grade('الصف ٢ ب'), 2)
        self.assertEqual(class_grade('الصف الرابع الأساسي'), 4)
        self.assertEqual(class_grade('الخامس أ'), 5)
        self.assertEqual(class_grade('السادسة ب'), 6)
        self.assertIsNone(class_grade('السابع أ'))
        self.assertIsNone(class_grade('الصف 12'))

    def test_book_type_is_limited_to_grades_one_through_six(self):
        self.assertEqual(grade_book_type(1), BOOK_TYPE_STAGE)
        self.assertEqual(grade_book_type(4), BOOK_TYPE_STAGE)
        self.assertEqual(grade_book_type(5), BOOK_TYPE_UPPER)
        self.assertEqual(grade_book_type(6), BOOK_TYPE_UPPER)
        self.assertIsNone(grade_book_type(7))

    def test_type_defaults_to_an_available_type(self):
        self.assertEqual(normalize_book_type('', {BOOK_TYPE_UPPER}), BOOK_TYPE_UPPER)
        self.assertEqual(normalize_book_type('invalid', {BOOK_TYPE_STAGE}), BOOK_TYPE_STAGE)
        self.assertEqual(normalize_book_type(BOOK_TYPE_UPPER, {BOOK_TYPE_STAGE}), BOOK_TYPE_UPPER)

    def test_manual_row_count_is_35_to_50_and_defaults_to_40(self):
        self.assertEqual(normalize_grade_row_count(35), 35)
        self.assertEqual(normalize_grade_row_count('50'), 50)
        self.assertEqual(normalize_grade_row_count(34), 40)
        self.assertEqual(normalize_grade_row_count(51), 40)
        self.assertEqual(len(build_grade_student_rows([], 35)), 35)
        self.assertEqual(len(build_grade_student_rows([], 50)), 50)

    def test_grade_label_keeps_the_recorded_class_name(self):
        self.assertEqual(grade_label(1, '1أ'), 'الصف الأول الأساسي (1أ)')


class GradeRegisterAccessTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='grade-admin', password='safe-password')
        Profile.objects.create(user=self.admin_user, role='admin')

        self.teacher_user = User.objects.create_user(username='grade-teacher', password='safe-password')
        Profile.objects.create(user=self.teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(user=self.teacher_user, full_name='سامي معلم الصفوف')

        self.other_user = User.objects.create_user(username='grade-other', password='safe-password')
        Profile.objects.create(user=self.other_user, role='teacher')
        self.other_teacher = Teacher.objects.create(user=self.other_user, full_name='معلم بلا جدول')

        self.stage_class = Class.objects.create(name='1أ')
        self.upper_class = Class.objects.create(name='الخامس ب')
        self.unknown_class = Class.objects.create(name='السابع أ')
        self.math = Subject.objects.create(name='الرياضيات')
        self.science = Subject.objects.create(name='العلوم')

        TeacherScheduleEntry.objects.create(
            teacher=self.teacher, day='الأحد', period=1,
            student_class=self.stage_class, subject=self.math,
        )
        # Repeated weekly periods must still produce one class-subject register.
        TeacherScheduleEntry.objects.create(
            teacher=self.teacher, day='الاثنين', period=2,
            student_class=self.stage_class, subject=self.math,
        )
        TeacherScheduleEntry.objects.create(
            teacher=self.teacher, day='الثلاثاء', period=3,
            student_class=self.stage_class, subject=self.science,
        )
        TeacherScheduleEntry.objects.create(
            teacher=self.teacher, day='الأربعاء', period=4,
            student_class=self.upper_class, subject=self.math,
        )
        TeacherScheduleEntry.objects.create(
            teacher=self.teacher, day='الخميس', period=5,
            student_class=self.unknown_class, subject=self.math,
        )

        for index, name in enumerate(('ياسر الطالب', 'أحمد الطالب'), start=1):
            user = User.objects.create_user(username=f'grade-student-{index}', password='safe-password')
            Profile.objects.create(user=user, role='student')
            Student.objects.create(
                user=user,
                student_id=f'55000{index}',
                full_name=name,
                student_class=self.stage_class,
            )
        self.student_user = User.objects.create_user(username='grade-blocked-student', password='safe-password')
        Profile.objects.create(user=self.student_user, role='student')

        SchoolInfo.objects.create(
            name_ar='ذكور المنصور الأساسية',
            principal_name='حسين حمامدة',
            national_number='12345',
        )

    def test_admin_selects_any_teacher_and_sees_distinct_stage_assignments(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('grade_register'), {'teacher': self.teacher.id, 'book_type': 'stage'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_teacher'], self.teacher)
        self.assertEqual(len(response.context['assignments']), 2)
        self.assertEqual(response.context['page_count'], 4)
        self.assertEqual(response.context['row_count'], 40)
        self.assertContains(response, '1أ')
        self.assertContains(response, 'الخامس ب')
        self.assertContains(response, 'معلم بلا جدول')
        self.assertContains(response, 'توجد 1 ارتباطات لم يمكن تحديد مرحلتها')

    def test_teacher_sees_menu_and_cannot_switch_to_another_teacher(self):
        self.client.force_login(self.teacher_user)

        dashboard = self.client.get(reverse('dashboard'))
        response = self.client.get(reverse('grade_register'), {
            'teacher': self.other_teacher.id,
            'book_type': 'upper',
        })

        self.assertContains(dashboard, 'دفتر العلامات')
        self.assertEqual(response.context['selected_teacher'], self.teacher)
        self.assertEqual(response.context['book_type'], BOOK_TYPE_UPPER)
        self.assertEqual(len(response.context['assignments']), 1)

    def test_student_cannot_open_grade_register_pages(self):
        self.client.force_login(self.student_user)

        for name in ('grade_register', 'grade_register_cover', 'grade_register_print'):
            response = self.client.get(reverse(name), {'teacher': self.teacher.id})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse('dashboard'))

    def test_stage_print_has_two_pages_per_assignment_months_and_sorted_names(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('grade_register_print'), {
            'teacher': self.teacher.id,
            'book_type': 'stage',
            'year': 2026,
            'rows': 35,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.count(b'data-page-kind="grade-marks"'), 4)
        self.assertEqual(len(response.context['assignments'][0]['student_rows']), 35)
        self.assertEqual(response.context['assignments'][0]['student_rows'][0]['name'], 'أحمد الطالب')
        self.assertContains(response, 'الصف الأول الأساسي (1أ)', count=4)
        for month in ('أيلول', 'تشرين الأول', 'تشرين الثاني', 'كانون الأول', 'شباط', 'آذار', 'نيسان', 'أيار'):
            self.assertContains(response, month, count=2)
        self.assertNotContains(response, 'ملحوظات مهمة')
        self.assertNotContains(response, 'علامة<br>الإكمال')

    def test_upper_print_uses_weighted_columns_and_makeup_only_in_second_semester(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('grade_register_print'), {
            'teacher': self.teacher.id,
            'book_type': 'upper',
            'year': 2026,
            'rows': 50,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.count(b'data-page-kind="grade-marks"'), 2)
        self.assertContains(response, 'الصف الخامس الأساسي (الخامس ب)', count=2)
        self.assertContains(response, 'اختبار<br>قصير 1', count=2)
        self.assertContains(response, '10%', count=4)
        self.assertContains(response, '20%', count=4)
        self.assertContains(response, '40%', count=2)
        self.assertContains(response, 'علامة<br>الإكمال', count=1)

    def test_cover_lists_all_distinct_recognized_classes_without_instructions(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('grade_register_cover'), {
            'teacher': self.teacher.id,
            'book_type': 'stage',
            'year': 2026,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'سامي معلم الصفوف')
        self.assertContains(response, '1أ')
        self.assertContains(response, 'الخامس ب')
        self.assertContains(response, '2026/2027')
        self.assertContains(response, 'حسين حمامدة')
        self.assertNotContains(response, 'السابع أ')
        self.assertNotContains(response, 'ملحوظات مهمة')
        self.assertEqual(response.content.count(b'data-page-kind="grade-cover"'), 1)

    def test_teacher_without_schedule_sees_page_but_cannot_print(self):
        self.client.force_login(self.other_user)

        page = self.client.get(reverse('grade_register'))
        printed = self.client.get(reverse('grade_register_print'))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'لا توجد صفوف ومباحث')
        self.assertRedirects(printed, reverse('grade_register'))
