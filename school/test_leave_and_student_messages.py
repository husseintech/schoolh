from datetime import time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Class, Message, Profile, Student, StudentLeave, Teacher, UserPermission


class LeavePermissionTests(TestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user('teacher-secure', password='test-pass')
        Profile.objects.create(user=self.teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(user=self.teacher_user, full_name='المعلم الآمن')
        self.own_class = Class.objects.create(name='1أ')
        self.other_class = Class.objects.create(name='2أ')
        self.teacher.classes.add(self.own_class)
        self.own_student = self._student('student-own', '10001', 'طالب الشعبة', self.own_class)
        self.other_student = self._student('student-other', '10002', 'طالب آخر', self.other_class)
        self.client.force_login(self.teacher_user)

    def _student(self, username, student_id, full_name, student_class):
        user = User.objects.create_user(username, password='test-pass')
        Profile.objects.create(user=user, role='student')
        return Student.objects.create(
            user=user,
            student_id=student_id,
            full_name=full_name,
            student_class=student_class,
        )

    def test_teacher_without_permission_cannot_open_or_create_leave(self):
        UserPermission.objects.create(user=self.teacher_user, permissions={'leaves': []})

        response = self.client.post(reverse('add_leave_with_student', args=[self.own_student.id]), {
            'student': self.own_student.id,
            'leave_time': time(10, 0),
            'reason': 'اختبار',
        })

        self.assertRedirects(response, reverse('dashboard'))
        self.assertFalse(StudentLeave.objects.exists())
        student_page = self.client.get(reverse('student_list'))
        self.assertNotContains(student_page, reverse('add_leave_with_student', args=[self.own_student.id]))

    def test_authorized_teacher_can_create_leave_only_for_assigned_class(self):
        UserPermission.objects.create(
            user=self.teacher_user,
            permissions={'leaves': ['add'], 'students': ['view']},
        )
        response = self.client.post(reverse('add_leave_with_student', args=[self.own_student.id]), {
            'student': self.own_student.id,
            'leave_time': '10:00',
            'reason': 'موعد طبي',
        })
        self.assertRedirects(response, reverse('student_list'))
        self.assertEqual(StudentLeave.objects.filter(student=self.own_student).count(), 1)

        response = self.client.post(reverse('add_leave_with_student', args=[self.other_student.id]), {
            'student': self.other_student.id,
            'leave_time': '10:30',
            'reason': 'محاولة غير مسموحة',
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(StudentLeave.objects.filter(student=self.other_student).exists())


class StudentAdminMessageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('principal', first_name='مدير المدرسة', password='test-pass')
        Profile.objects.create(user=self.admin, role='admin')
        self.teacher = User.objects.create_user('teacher-target', first_name='معلم', password='test-pass')
        Profile.objects.create(user=self.teacher, role='teacher')
        Teacher.objects.create(user=self.teacher, full_name='المعلم الهدف')
        self.student = User.objects.create_user('student-sender', first_name='طالب', password='test-pass')
        Profile.objects.create(user=self.student, role='student')
        Student.objects.create(user=self.student, student_id='20001', full_name='الطالب المرسل')
        UserPermission.objects.create(user=self.student, permissions={'messages': ['send']})
        self.client.force_login(self.student)

    def test_student_sees_only_admin_accounts(self):
        response = self.client.get(reverse('send_message'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'يمكنك إرسال رسالتك بأمان إلى حسابات مدير المدرسة فقط')
        self.assertContains(response, 'مدير المدرسة')
        self.assertNotContains(response, 'المعلم الهدف')

    def test_student_cannot_bypass_recipient_restriction(self):
        get_response = self.client.get(reverse('send_message_to', args=[self.teacher.id]))
        self.assertEqual(get_response.status_code, 404)

        post_response = self.client.post(reverse('send_message'), {
            'recipient_id': self.teacher.id,
            'subject': 'غير مسموح',
            'content': 'لا يجب إنشاء هذه الرسالة',
        })
        self.assertEqual(post_response.status_code, 404)
        self.assertFalse(Message.objects.exists())

    def test_student_can_message_admin_and_admin_inbox_receives_it(self):
        response = self.client.post(reverse('send_message'), {
            'recipient_id': self.admin.id,
            'subject': 'طلب مساعدة',
            'content': 'رسالة إلى مدير المدرسة',
        })
        self.assertRedirects(response, reverse('send_message'))
        self.assertTrue(Message.objects.filter(sender=self.student, recipient=self.admin).exists())

        self.client.force_login(self.admin)
        inbox = self.client.get(reverse('message_list'))
        self.assertContains(inbox, 'طلب مساعدة')
