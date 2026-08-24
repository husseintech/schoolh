
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

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from school.models import (SchedulePlan, TeachingLoad, ScheduleEntry, Teacher,
                           Class, Subject, Profile)


class ScheduleViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('admin', password='pw')
        Profile.objects.create(user=self.user, role='admin')
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
                                    subject=self.subj, student_class=self.cls, weekly_periods=3)
        ScheduleEntry.objects.create(plan=self.plan, day='الأحد', period=1,
                                     teacher=self.teacher, subject=self.subj, student_class=self.cls)
        ScheduleEntry.objects.create(plan=self.plan, day='الأحد', period=2,
                                     teacher=self.teacher, subject=self.subj, student_class=self.cls)

    def test_pages_render(self):
        self.client.login(username='admin', password='pw')
        urls = [
            reverse('schedule_plan_list'),
            reverse('schedule_plan_detail', args=[self.plan.id]),
            reverse('schedule_plan_settings', args=[self.plan.id]),
            reverse('teaching_loads', args=[self.plan.id]),
            reverse('availability_grid', args=[self.plan.id]),
            reverse('availability_report', args=[self.plan.id]),
            reverse('schedule_constraints', args=[self.plan.id]),
            reverse('fixed_lessons', args=[self.plan.id]),
            reverse('schedule_generate', args=[self.plan.id]),
            reverse('schedule_grid', args=[self.plan.id]),
            reverse('schedule_edit_grid', args=[self.plan.id]),
            reverse('schedule_teachers', args=[self.plan.id]),
            reverse('schedule_classes', args=[self.plan.id]),
        ]
        for u in urls:
            r = self.client.get(u)
            self.assertEqual(r.status_code, 200, u)
