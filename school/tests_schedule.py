
from django.contrib.auth.models import User
from django.test import TestCase
from school.models import (SchedulePlan, TeachingLoad, TeacherAvailability,
                           ScheduleEntry, Teacher, Class, Subject, Profile,
                           ScheduleConstraint, FixedLesson)
from school.scheduling_engine import generate_schedule, evaluate_plan
from school.scheduling import ScheduleValidator


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

    def test_print_general_renders(self):
        from django.test import Client
        from django.urls import reverse
        res = generate_schedule(self.plan)
        ScheduleEntry.objects.bulk_create([
            ScheduleEntry(plan=self.plan, day=e['day'], period=e['period'], teacher_id=e['teacher'],
                          subject_id=e['subject'], student_class_id=e['class'], fixed=e['fixed'])
            for e in res['entries']
        ])
        Profile.objects.create(user=self.user, role='admin')
        c = Client()
        c.force_login(self.user)
        r = c.get(reverse('schedule_print_general', args=[self.plan.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'اليوم')
        self.assertContains(r, 'المادة')

    def test_teacher_class_views_render(self):
        from django.test import Client
        from django.urls import reverse
        res = generate_schedule(self.plan)
        ScheduleEntry.objects.bulk_create([
            ScheduleEntry(plan=self.plan, day=e['day'], period=e['period'], teacher_id=e['teacher'],
                          subject_id=e['subject'], student_class_id=e['class'], fixed=e['fixed'])
            for e in res['entries']
        ])
        Profile.objects.create(user=self.user, role='admin')
        c = Client()
        c.force_login(self.user)
        self.assertEqual(c.get(reverse('schedule_teacher', args=[self.plan.id, self.teacher.id])).status_code, 200)
        self.assertEqual(c.get(reverse('schedule_class', args=[self.plan.id, self.cls.id])).status_code, 200)

    def test_teacher_report_renders(self):
        from django.test import Client
        from django.urls import reverse
        res = generate_schedule(self.plan)
        ScheduleEntry.objects.bulk_create([
            ScheduleEntry(plan=self.plan, day=e['day'], period=e['period'], teacher_id=e['teacher'],
                          subject_id=e['subject'], student_class_id=e['class'], fixed=e['fixed'])
            for e in res['entries']
        ])
        Profile.objects.create(user=self.user, role='admin')
        c = Client()
        c.force_login(self.user)
        r = c.get(reverse('schedule_teacher_report', args=[self.plan.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'عدد الحصص')

    def test_evaluate_detects_availability_conflict(self):
        ScheduleEntry.objects.create(plan=self.plan, day='الأحد', period=1,
                                     teacher=self.teacher, subject=self.subj,
                                     student_class=self.cls)
        res = evaluate_plan(self.plan)
        self.assertLess(res['hard_score'], 100.0)
        self.assertTrue(any(c['type'] == 'availability' for c in res['conflicts']))

    def test_parallel_classes_both_scheduled(self):
        cls2 = Class.objects.create(name='أولى ب')
        u2 = User.objects.create_user('tuser2', password='x')
        t2 = Teacher.objects.create(full_name='معلم2', user=u2)
        sub2 = Subject.objects.create(name='علوم')
        TeachingLoad.objects.create(plan=self.plan, teacher=t2, subject=sub2,
                                    student_class=cls2, weekly_periods=3)
        for d in self.plan.active_days:
            for p in self.plan.active_periods:
                TeacherAvailability.objects.create(plan=self.plan, teacher=t2,
                                                   day=d['name'], period=p['idx'], available=True)
        res = generate_schedule(self.plan)
        self.assertEqual(len(res['unscheduled']), 0)
        keys = [(e['class'], e['day'], e['period']) for e in res['entries']]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(res['entries']), 6)
        ScheduleEntry.objects.bulk_create([
            ScheduleEntry(plan=self.plan, day=e['day'], period=e['period'],
                          teacher_id=e['teacher'], subject_id=e['subject'],
                          student_class_id=e['class'], fixed=e['fixed'])
            for e in res['entries']
        ])
        self.assertEqual(ScheduleEntry.objects.filter(plan=self.plan).count(), 6)

    def test_hillclimb_no_crash(self):
        days = [{'idx': i, 'name': 'يوم%d' % i, 'active': True} for i in range(5)]
        periods = [{'idx': i, 'name': 'حصة%d' % i, 'active': True} for i in range(6)]
        plan = SchedulePlan.objects.create(name='كبيرة', academic_year='2025',
                                            days=days, periods=periods)
        subs = [Subject.objects.create(name='م%d' % i) for i in range(3)]
        clss = [Class.objects.create(name='ص%d' % i) for i in range(3)]
        teachers = []
        for i in range(3):
            u = User.objects.create_user('ht%d' % i, password='x')
            teachers.append(Teacher.objects.create(full_name='معلم%d' % i, user=u))
        for t in teachers:
            for c in clss:
                TeachingLoad.objects.create(plan=plan, teacher=t, subject=subs[0],
                                            student_class=c, weekly_periods=2)
        res = generate_schedule(plan)
        self.assertTrue(isinstance(len(res['entries']), int))
        keys = [(e['class'], e['day'], e['period']) for e in res['entries']]
        self.assertEqual(len(keys), len(set(keys)))

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

    def test_edit_constraint(self):
        from school.models import ScheduleConstraint
        c = ScheduleConstraint.objects.create(plan=self.plan, type='soft', code='max_consecutive',
                                               label='قديم', weight=2, scope='all', params={})
        self.client.login(username='admin', password='pw')
        r = self.client.post(reverse('schedule_constraints', args=[self.plan.id]), {
            'action': 'edit', 'cid': c.id, 'code': 'max_consecutive',
            'label': 'جديد', 'type': 'hard', 'weight': 5, 'scope': 'all',
        })
        self.assertEqual(r.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.label, 'جديد')
        self.assertEqual(c.type, 'hard')
        self.assertEqual(c.weight, 5.0)

    def test_load_add_and_delete(self):
        from school.models import TeachingLoad
        self.client.login(username='admin', password='pw')
        r = self.client.post(reverse('teaching_loads', args=[self.plan.id]), {
            'action': 'save', 'teacher': self.teacher.id, 'subject': self.subj.id,
            'student_class': self.cls.id, 'weekly_periods': 4, 'semester': ''})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(TeachingLoad.objects.filter(plan=self.plan).count(), 1)
        lid = TeachingLoad.objects.filter(plan=self.plan).first().id
        r = self.client.post(reverse('teaching_loads', args=[self.plan.id]), {
            'action': 'delete', 'load_id': lid})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(TeachingLoad.objects.filter(plan=self.plan).count(), 0)

    def test_fixed_delete(self):
        from school.models import FixedLesson
        self.client.login(username='admin', password='pw')
        fl = FixedLesson.objects.create(plan=self.plan, day='الأحد', period=1,
            teacher=self.teacher, subject=self.subj, student_class=self.cls)
        r = self.client.post(reverse('fixed_lessons', args=[self.plan.id]), {
            'action': 'delete', 'fixed_id': fl.id})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(FixedLesson.objects.filter(plan=self.plan).count(), 0)

class ScheduleConstraintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cuser', password='pw')
        Profile.objects.create(user=self.user, role='admin')
        self.subj = Subject.objects.create(name='رياضيات')
        self.cls = Class.objects.create(name='أولى أ')
        self.teacher = Teacher.objects.create(full_name='معلم', user=self.user)
        self.plan = SchedulePlan.objects.create(
            name='خطة', academic_year='2025',
            days=[{'idx': 0, 'name': 'الأحد', 'active': True},
                  {'idx': 1, 'name': 'الإثنين', 'active': True},
                  {'idx': 2, 'name': 'الثلاثاء', 'active': True}],
            periods=[{'idx': 1, 'name': 'الحصة 1', 'active': True},
                     {'idx': 2, 'name': 'الحصة 2', 'active': True}],
        )
        TeachingLoad.objects.create(plan=self.plan, teacher=self.teacher,
                                    subject=self.subj, student_class=self.cls, weekly_periods=3)
        # constraints
        ScheduleConstraint.objects.create(plan=self.plan, type='soft', code='spread_subject',
                                          label='توزيع', enabled=True, weight=1, params={'max_per_day': 1})
        ScheduleConstraint.objects.create(plan=self.plan, type='soft', code='max_consecutive_gap',
                                          label='فراغ', enabled=True, weight=1, params={'max_gap': 1})
        ScheduleConstraint.objects.create(plan=self.plan, type='soft', code='period_repeat',
                                          label='تكرار حصة 1', enabled=True, weight=1,
                                          params={'period': 1, 'max_days': 1})

    def test_constraints_respected(self):
        from school.scheduling_engine import generate_schedule, evaluate_plan
        res = generate_schedule(self.plan)
        # store
        ScheduleEntry.objects.filter(plan=self.plan).delete()
        for e in res['entries']:
            ScheduleEntry.objects.create(plan=self.plan, day=e['day'], period=e['period'],
                                         teacher=Teacher.objects.get(id=e['teacher']),
                                         subject=Subject.objects.get(id=e['subject']),
                                         student_class=Class.objects.get(id=e['class']),
                                         fixed=e['fixed'], color='')
        ev = evaluate_plan(self.plan)
        bad = [c for c in ev['conflicts'] if c['type'] in ('spread', 'gap', 'period_repeat')]
        self.assertEqual(bad, [], msg=ev['conflicts'])
        self.assertEqual(len(res['entries']), 3)

class NLPTests(TestCase):
    def test_parse_teacher_consecutive(self):
        from school.constraint_nlp import parse_constraint_text
        u=User.objects.create_user('nlp',password='x')
        Profile.objects.create(user=u,role='admin')
        t=Teacher.objects.create(full_name='احمد علي',user=u)
        c=Class.objects.create(name='الصف الاول')
        subj=Subject.objects.create(name='رياضيات')
        plan=SchedulePlan.objects.create(name='p',academic_year='2025',
            days=[{'idx':0,'name':'الاحد','active':True}],periods=[{'idx':1,'name':'1','active':True}])
        TeachingLoad.objects.create(plan=plan,teacher=t,subject=subj,student_class=c,weekly_periods=2)
        r=parse_constraint_text('المعلم احمد علي لا يزيد عن 3 حصص متتالية',plan)
        self.assertIsNotNone(r)
        self.assertEqual(r['code'],'max_consecutive')
        self.assertEqual(r['scope'],'teachers')
        self.assertIn(t.id,r['teacher_ids'])
        self.assertEqual(r['weight'],3.0)


class CpSatSolverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cp', password='x')
        self.subj = Subject.objects.create(name='عربي')
        self.cls = Class.objects.create(name='تاسع')
        self.teacher = Teacher.objects.create(full_name='م ع', user=self.user)

    def _make_plan(self, ndays=2, nperiods=2):
        days = [{'idx': i, 'name': 'يوم%d' % i, 'active': True} for i in range(ndays)]
        periods = [{'idx': i, 'name': 'حصة%d' % i, 'active': True} for i in range(nperiods)]
        return SchedulePlan.objects.create(name='cp', academic_year='2025', days=days, periods=periods)

    def _fill_availability(self, plan):
        for d in plan.active_days:
            for p in plan.active_periods:
                TeacherAvailability.objects.create(plan=plan, teacher=self.teacher,
                                                   day=d['name'], period=p['idx'], available=True)

    def test_cp_solver_success(self):
        plan = self._make_plan(2, 2)
        TeachingLoad.objects.create(plan=plan, teacher=self.teacher, subject=self.subj,
                                    student_class=self.cls, weekly_periods=3)
        self._fill_availability(plan)
        res = generate_schedule(plan)
        self.assertEqual(res['status'], 'SUCCESS')
        self.assertEqual(len(res['entries']), 3)
        self.assertEqual(res['hard_score'], 100.0)

    def test_cp_infeasible_capacity(self):
        plan = self._make_plan(2, 2)  # السعة = 4
        TeachingLoad.objects.create(plan=plan, teacher=self.teacher, subject=self.subj,
                                    student_class=self.cls, weekly_periods=5)  # > السعة
        self._fill_availability(plan)
        res = generate_schedule(plan)
        self.assertEqual(res['status'], 'INFEASIBLE')
        self.assertTrue(res['diagnostics'])

    def test_validator_detects_availability(self):
        plan = self._make_plan(2, 2)
        TeacherAvailability.objects.create(plan=plan, teacher=self.teacher,
                                           day='يوم0', period=0, available=False)
        ScheduleEntry.objects.create(plan=plan, day='يوم0', period=0,
                                     teacher=self.teacher, subject=self.subj, student_class=self.cls)
        v = ScheduleValidator(plan)
        self.assertFalse(v['valid'])
        self.assertTrue(any('توفّر' in x for x in v['violations']))

    def test_fixed_lesson_enforced(self):
        plan = self._make_plan(2, 2)
        TeachingLoad.objects.create(plan=plan, teacher=self.teacher, subject=self.subj,
                                    student_class=self.cls, weekly_periods=2)
        self._fill_availability(plan)
        FixedLesson.objects.create(plan=plan, day='يوم0', period=0, teacher=self.teacher,
                                   subject=self.subj, student_class=self.cls)
        res = generate_schedule(plan)
        self.assertEqual(res['status'], 'SUCCESS')
        fixed = [e for e in res['entries'] if e['day'] == 'يوم0' and e['period'] == 0]
        self.assertEqual(len(fixed), 1)
        self.assertTrue(fixed[0]['fixed'])

    def test_realistic_school_fixture(self):
        plan = self._make_plan(5, 7)
        teachers, classes, subjects = [], [], []
        for i in range(10):
            u = User.objects.create_user('rt%d' % i, password='x')
            teachers.append(Teacher.objects.create(full_name='معلم%d' % i, user=u))
        for i in range(5):
            classes.append(Class.objects.create(name='ش%d' % i))
        for i in range(6):
            subjects.append(Subject.objects.create(name='مادة%d' % i))
        for t in teachers:
            for c in classes[:3]:
                TeachingLoad.objects.create(plan=plan, teacher=t, subject=subjects[t.id % 6],
                                            student_class=c, weekly_periods=3)
        self._fill_availability(plan)
        for t in teachers:
            for c in classes[3:]:
                TeachingLoad.objects.create(plan=plan, teacher=t, subject=subjects[(t.id + 1) % 6],
                                            student_class=c, weekly_periods=2)
        res = generate_schedule(plan)
        self.assertEqual(res['status'], 'SUCCESS')
        self.assertEqual(res['hard_score'], 100.0)
        from collections import Counter
        ccls = Counter((e['class'], e['day'], e['period']) for e in res['entries'])
        cteach = Counter((e['teacher'], e['day'], e['period']) for e in res['entries'])
        self.assertEqual([k for k, v in ccls.items() if v > 1], [],
                         msg='class-double: %s' % [k for k, v in ccls.items() if v > 1])
        self.assertEqual([k for k, v in cteach.items() if v > 1], [],
                         msg='teacher-double: %s' % [k for k, v in cteach.items() if v > 1])
        total = sum(t.weekly_periods for t in TeachingLoad.objects.filter(plan=plan))
        self.assertEqual(len(res['entries']), total)
        ScheduleEntry.objects.bulk_create([
            ScheduleEntry(plan=plan, day=e['day'], period=e['period'], teacher_id=e['teacher'],
                          subject_id=e['subject'], student_class_id=e['class'], fixed=e['fixed'])
            for e in res['entries']
        ])
        v = ScheduleValidator(plan)
        self.assertTrue(v['valid'], msg=v['violations'])
