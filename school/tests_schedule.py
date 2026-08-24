
from django.contrib.auth.models import User
from django.test import TestCase
from school.models import (SchedulePlan, TeachingLoad, TeacherAvailability,
                           ScheduleEntry, Teacher, Class, Subject)
from school.scheduling_engine import generate_schedule, evaluate_plan


class ScheduleEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tuser', password='x')
        self.subj = Subject.objects.create(name='رياضيات')
        self.cls = Class.objects.create(name='أولى أ')
        self.teacher = Teacher.objects.create(full_name='معلم', user=self.user)
        self.plan = SchedulePlan.objects.create(
            name='خطة', academic_year='2025',
            days=[{'idx': 0, 'name': 'الأحد', 'active': True},
                  {'idx': 1, 'name': 'الإثنين', 'active': True}],
            periods=[{'idx': 1, 'name': 'الحصة 1', 'active': True},
                     {'idx': 2, 'name': 'الحصة 2', 'active': True}],
        )
        TeachingLoad.objects.create(plan=self.plan, teacher=self.teacher,
                                    subject=self.subj, student_class=self.cls,
                                    weekly_periods=3)
        for d in self.plan.active_days:
            for p in self.plan.active_periods:
                av = True
                if d['name'] == 'الأحد' and p['idx'] == 1:
                    av = False
                TeacherAvailability.objects.create(plan=self.plan, teacher=self.teacher,
                                                   day=d['name'], period=p['idx'], available=av)

    def test_generate_produces_entries(self):
        res = generate_schedule(self.plan)
        self.assertEqual(len(res['unscheduled']), 0)
        self.assertEqual(len(res['conflicts']), 0)
        self.assertEqual(res['hard_score'], 100.0)
        self.assertEqual(len(res['entries']), 3)

    def test_evaluate_detects_availability_conflict(self):
        ScheduleEntry.objects.create(plan=self.plan, day='الأحد', period=1,
                                     teacher=self.teacher, subject=self.subj,
                                     student_class=self.cls)
        res = evaluate_plan(self.plan)
        self.assertLess(res['hard_score'], 100.0)
        self.assertTrue(any(c['type'] == 'availability' for c in res['conflicts']))
