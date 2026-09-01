from django.test import TestCase
from django.contrib.auth.models import User
from .models import Teacher, Subject, Class
from .teacher_records_models import CurriculumProgressRecord, TeacherTrainingRecord


class TeacherRecordsTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('teacher-record-test')
        self.teacher=Teacher.objects.create(user=self.user,full_name='معلم اختبار')
        self.subject=Subject.objects.create(name='مادة اختبار السجلات')
        self.cls=Class.objects.create(name='صف اختبار السجلات')

    def test_remaining_pages(self):
        r=CurriculumProgressRecord.objects.create(teacher=self.teacher,subject=self.subject,student_class=self.cls,record_date='2026-09-01',academic_year='2026/2027',assigned_pages=100,completed_pages=65,created_by=self.user)
        self.assertEqual(r.remaining_pages,35)

    def test_training_record(self):
        r=TeacherTrainingRecord.objects.create(teacher=self.teacher,course_date='2026-09-01',course_name='دورة اختبار',created_by=self.user)
        self.assertEqual(r.teacher,self.teacher)
