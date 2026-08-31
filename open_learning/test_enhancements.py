from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from school.models import Class, Profile, Student, Subject, Teacher

from .enhancement_models import GuardianStudentLink, RemediationPlan
from .learning_models import LessonQuiz, QuizAttempt, QuizQuestion
from .models import LearningLesson
from .services.smart_assessment import generate_quiz_draft


class FullLearningEnhancementTests(TestCase):
    def setUp(self):
        self.student_class = Class.objects.create(name='صف حزمة التعلم')
        self.other_class = Class.objects.create(name='صف آخر للحزمة')
        self.subject = Subject.objects.create(name='رياضيات الحزمة')

        self.teacher_user = User.objects.create_user('suite_teacher', password='pass12345')
        Profile.objects.create(user=self.teacher_user, role='teacher')
        self.teacher = Teacher.objects.create(user=self.teacher_user, full_name='معلم الحزمة')
        self.teacher.classes.add(self.student_class)
        self.teacher.subjects.add(self.subject)

        self.student_user = User.objects.create_user('suite_student', password='pass12345')
        Profile.objects.create(user=self.student_user, role='student')
        self.student = Student.objects.create(
            user=self.student_user, student_id='88220011', full_name='طالب الحزمة', student_class=self.student_class
        )
        self.lesson = LearningLesson.objects.create(
            title='الضرب', description='تدريب على عملية الضرب', subject=self.subject,
            teacher=self.teacher, status='published',
        )
        self.lesson.student_classes.add(self.student_class)

    def test_local_smart_quiz_is_topic_specific_for_multiplication(self):
        draft = generate_quiz_draft(self.lesson, count=5, difficulty='medium')
        self.assertEqual(len(draft['questions']), 5)
        self.assertTrue(all('×' in question['text'] for question in draft['questions']))
        for question in draft['questions']:
            self.assertIn(question['correct_answer'], question['options'])

    def test_smart_quiz_endpoint_creates_unpublished_draft(self):
        self.client.login(username='suite_teacher', password='pass12345')
        response = self.client.post(
            reverse('ol_smart_quiz_generate', args=[self.lesson.id]),
            {'question_count': '5', 'difficulty': 'medium'},
        )
        self.assertEqual(response.status_code, 302)
        quiz = LessonQuiz.objects.filter(lesson=self.lesson).latest('id')
        self.assertFalse(quiz.is_published)
        self.assertEqual(quiz.questions.count(), 5)

    def test_failed_quiz_creates_remediation_plan(self):
        quiz = LessonQuiz.objects.create(
            lesson=self.lesson, title='اختبار علاجي', is_published=True, passing_score=60, max_attempts=2
        )
        question = QuizQuestion.objects.create(
            quiz=quiz, text='3 × 4 = ؟', options=['7', '12'], correct_answer='12', points=1
        )
        self.client.login(username='suite_student', password='pass12345')
        response = self.client.post(reverse('ol_quiz_take', args=[quiz.id]), {f'q_{question.id}': '7'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(RemediationPlan.objects.filter(student=self.student, quiz=quiz, status='active').exists())

    def test_guardian_can_only_see_linked_child(self):
        other_user = User.objects.create_user('suite_other_student', password='pass12345')
        Profile.objects.create(user=other_user, role='student')
        other_student = Student.objects.create(
            user=other_user, student_id='88220012', full_name='طالب آخر', student_class=self.other_class
        )
        guardian = User.objects.create_user('suite_guardian', password='pass12345')
        Profile.objects.create(user=guardian, role='guardian')
        GuardianStudentLink.objects.create(guardian=guardian, student=self.student)

        self.client.login(username='suite_guardian', password='pass12345')
        allowed = self.client.get(reverse('ol_guardian_student_detail', args=[self.student.id]))
        denied = self.client.get(reverse('ol_guardian_student_detail', args=[other_student.id]))
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 404)

    def test_guardian_is_redirected_away_from_teacher_dashboard(self):
        guardian = User.objects.create_user('suite_guardian_two', password='pass12345')
        Profile.objects.create(user=guardian, role='guardian')
        GuardianStudentLink.objects.create(guardian=guardian, student=self.student)
        self.client.login(username='suite_guardian_two', password='pass12345')
        response = self.client.get(reverse('ol_teacher_learning_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('ol_guardian_portal'), response.url)
