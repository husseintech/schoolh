from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from school.models import Class, Profile, Student, Subject, Teacher
from .models import LearningLesson
from .progress_models import StudentLessonProgress
from .learning_models import LessonQuiz, QuizQuestion, QuizAttempt, LessonAssignment, AssignmentSubmission


class OpenLearningStudentFlowTests(TestCase):
    def setUp(self):
        self.class_a = Class.objects.create(name='اختبار أ')
        self.class_b = Class.objects.create(name='اختبار ب')
        self.subject = Subject.objects.create(name='مادة اختبار')

        teacher_user = User.objects.create_user('teacher_test', password='pass12345')
        Profile.objects.create(user=teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(user=teacher_user, full_name='معلم اختبار')
        self.teacher.classes.add(self.class_a, self.class_b)
        self.teacher.subjects.add(self.subject)

        student_user = User.objects.create_user('student_a', password='pass12345')
        Profile.objects.create(user=student_user, role='student')
        self.student = Student.objects.create(user=student_user, student_id='99110011', full_name='طالب أ', student_class=self.class_a)

        self.lesson_a = LearningLesson.objects.create(title='درس الصف أ', subject=self.subject, teacher=self.teacher, status='published')
        self.lesson_a.student_classes.add(self.class_a)
        self.lesson_b = LearningLesson.objects.create(title='درس الصف ب', subject=self.subject, teacher=self.teacher, status='published')
        self.lesson_b.student_classes.add(self.class_b)
        self.client.login(username='student_a', password='pass12345')

    def test_student_can_open_own_class_learning_path(self):
        response = self.client.get(reverse('ol_student_learning_path', args=[self.lesson_a.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'درس الصف أ')

    def test_student_cannot_open_other_class_learning_path(self):
        response = self.client.get(reverse('ol_student_learning_path', args=[self.lesson_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_opening_learning_path_starts_progress(self):
        self.client.get(reverse('ol_student_learning_path', args=[self.lesson_a.id]))
        progress = StudentLessonProgress.objects.get(student=self.student, lesson=self.lesson_a)
        self.assertEqual(progress.status, StudentLessonProgress.STATUS_IN_PROGRESS)

    def test_quiz_is_graded_automatically(self):
        quiz = LessonQuiz.objects.create(lesson=self.lesson_a, title='اختبار قصير', is_published=True, passing_score=50, max_attempts=2)
        question = QuizQuestion.objects.create(quiz=quiz, text='2+2؟', options=['3', '4'], correct_answer='4', points=2)
        response = self.client.post(reverse('ol_quiz_take', args=[quiz.id]), {f'q_{question.id}': '4'})
        self.assertEqual(response.status_code, 302)
        attempt = QuizAttempt.objects.get(student=self.student, quiz=quiz)
        self.assertEqual(float(attempt.percentage), 100.0)
        self.assertTrue(attempt.passed)

    def test_assignment_submission_is_unique_and_editable(self):
        assignment = LessonAssignment.objects.create(lesson=self.lesson_a, title='واجب', instructions='أجب', is_published=True)
        url = reverse('ol_assignment_submit', args=[assignment.id])
        self.client.post(url, {'answer_text': 'الإجابة الأولى'})
        self.client.post(url, {'answer_text': 'الإجابة المعدلة'})
        self.assertEqual(AssignmentSubmission.objects.filter(student=self.student, assignment=assignment).count(), 1)
        self.assertEqual(AssignmentSubmission.objects.get(student=self.student, assignment=assignment).answer_text, 'الإجابة المعدلة')
