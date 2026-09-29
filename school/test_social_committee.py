from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from school.models import (
    Profile, SocialCommitteeExpense, SocialCommitteePayment,
    Teacher, UserPermission,
)
from school.views import get_clearable_tables, permission_schema


class SocialCommitteeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='committee-admin', password='test-password')
        Profile.objects.create(user=self.admin, role='admin')
        self.teachers = []
        for index, name in enumerate(('أحمد علي', 'باسم حسن'), 1):
            user = User.objects.create_user(username=f'committee-teacher-{index}', password='test-password')
            Profile.objects.create(user=user, role='teacher')
            self.teachers.append(Teacher.objects.create(user=user, full_name=name))
        self.url = reverse('social_committee')

    def _pay(self, month, amount, notes='', teacher=None):
        teacher = teacher or self.teachers[0]
        return SocialCommitteePayment.objects.create(
            teacher=teacher, teacher_name=teacher.full_name,
            year=2026, month=month, amount=Decimal(amount), notes=notes,
        )

    def test_monthly_entry_reports_and_annual_balance(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {'year': 2026, 'month': 9})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'اللجنة الاجتماعية')
        self.assertContains(response, 'أحمد علي')
        self.assertContains(response, 'باسم حسن')
        self.assertContains(response, 'value="9" selected')
        self.assertContains(response, 'social-committee/report/')

        response = self.client.post(self.url, {
            'year': 2026, 'month': 9, 'action': 'save_payments',
            f'amount_{self.teachers[0].id}': '25.50',
            f'notes_{self.teachers[0].id}': 'دفعة أولى',
            f'amount_{self.teachers[1].id}': '',
        })
        self.assertRedirects(response, f'{self.url}?year=2026&month=9')
        self.assertEqual(SocialCommitteePayment.objects.count(), 1)
        self.assertEqual(SocialCommitteePayment.objects.get().amount, Decimal('25.50'))
        self.client.post(self.url, {'year': 2026, 'month': 9, 'action': 'add_expense',
                                    'item': 'ضيافة', 'amount': '30.00', 'notes': 'اجتماع'})
        self.client.post(self.url, {'year': 2026, 'month': 10, 'action': 'add_expense',
                                    'item': 'قرطاسية', 'amount': '5.00'})

        month = self.client.get(self.url, {'year': 2026, 'month': 9})
        self.assertEqual(month.context['income'], Decimal('25.50'))
        self.assertEqual(month.context['spending'], Decimal('30.00'))
        self.assertEqual(month.context['deficit'], Decimal('4.50'))
        self.assertEqual(month.context['annual_spending'], Decimal('35.00'))
        self.assertEqual(len(month.context['unpaid']), 1)

        paid = self.client.get(reverse('social_committee_report'), {'year': 2026, 'month': 9, 'kind': 'paid'})
        unpaid = self.client.get(reverse('social_committee_report'), {'year': 2026, 'month': 9, 'kind': 'unpaid'})
        purchases = self.client.get(reverse('social_committee_report'), {'year': 2026, 'month': 9, 'kind': 'expenses'})
        annual = self.client.get(reverse('social_committee_report'), {'year': 2026, 'kind': 'annual'})
        self.assertEqual([row['teacher'] for row in paid.context['paid']], [self.teachers[0]])
        self.assertEqual([row['teacher'] for row in unpaid.context['unpaid']], [self.teachers[1]])
        self.assertContains(purchases, 'ضيافة')
        self.assertNotContains(purchases, 'قرطاسية')
        self.assertEqual(annual.context['annual_income'], Decimal('25.50'))
        self.assertEqual(annual.context['annual_spending'], Decimal('35.00'))
        self.assertEqual(annual.context['annual_balance'], Decimal('-9.50'))
        self.assertContains(annual, 'قرطاسية')

    def test_invalid_batch_does_not_partially_change_payments(self):
        self.client.force_login(self.admin)
        self._pay(9, '10.00')
        response = self.client.post(self.url, {
            'year': 2026, 'month': 9, 'action': 'save_payments',
            f'amount_{self.teachers[0].id}': '20.00',
            f'amount_{self.teachers[1].id}': '-3.00',
        })
        self.assertRedirects(response, f'{self.url}?year=2026&month=9')
        self.assertEqual(SocialCommitteePayment.objects.get().amount, Decimal('10.00'))
        self.assertEqual(SocialCommitteePayment.objects.count(), 1)

    def test_expense_edit_delete_and_historical_payment_after_teacher_delete(self):
        self.client.force_login(self.admin)
        payment = self._pay(9, '15.00')
        self.teachers[0].delete()
        payment.refresh_from_db()
        self.assertIsNone(payment.teacher)
        report = self.client.get(reverse('social_committee_report'), {'year': 2026, 'month': 9, 'kind': 'paid'})
        self.assertContains(report, 'أحمد علي')
        self.assertEqual(report.context['income'], Decimal('15.00'))
        expense = SocialCommitteeExpense.objects.create(year=2026, month=9, item='قديم', amount=Decimal('4.00'))
        endpoint = reverse('social_committee_expense', args=[expense.pk])
        self.assertEqual(self.client.get(endpoint).status_code, 405)
        self.client.post(endpoint, {'action': 'edit', 'item': 'جديد', 'amount': '7.25', 'notes': 'فاتورة'})
        expense.refresh_from_db()
        self.assertEqual((expense.item, expense.amount), ('جديد', Decimal('7.25')))
        self.client.post(endpoint, {'action': 'delete'})
        self.assertFalse(SocialCommitteeExpense.objects.filter(pk=expense.pk).exists())

    def test_permissions_restrict_teacher_access_and_mutations(self):
        self.assertEqual(permission_schema()['social_committee'], ['view', 'add', 'edit', 'delete', 'print'])
        user = self.teachers[0].user
        self.client.force_login(user)
        self.assertRedirects(self.client.get(self.url), reverse('dashboard'))
        self.assertRedirects(self.client.get(reverse('social_committee_report')), reverse('dashboard'))
        self.assertNotContains(self.client.get(reverse('dashboard')), self.url)

        permissions = UserPermission.objects.create(user=user, permissions={'social_committee': ['view']})
        self.assertContains(self.client.get(reverse('dashboard')), self.url)
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'حفظ مدفوعات الشهر')
        self.assertNotContains(page, 'تقارير قابلة للطباعة')
        self.client.post(self.url, {'year': 2026, 'month': 9, 'action': 'add_expense', 'item': 'ممنوع', 'amount': '2'})
        self.client.post(self.url, {'year': 2026, 'month': 9, 'action': 'save_payments',
                                    f'amount_{self.teachers[0].id}': '2'})
        self.assertFalse(SocialCommitteeExpense.objects.exists())
        self.assertFalse(SocialCommitteePayment.objects.exists())

        permissions.permissions = {'social_committee': ['view', 'add']}
        permissions.save()
        self.client.post(self.url, {'year': 2026, 'month': 9, 'action': 'save_payments',
                                    f'amount_{self.teachers[0].id}': '2'})
        self.assertEqual(SocialCommitteePayment.objects.get().amount, Decimal('2.00'))
        self.client.post(self.url, {'year': 2026, 'month': 9, 'action': 'save_payments',
                                    f'amount_{self.teachers[0].id}': '3'})
        self.assertEqual(SocialCommitteePayment.objects.get().amount, Decimal('2.00'))

    def test_maintenance_clears_both_tables_without_deleting_teachers(self):
        self.assertIn('social_committee', {key for key, *_ in get_clearable_tables()})
        self._pay(9, '8.00')
        SocialCommitteeExpense.objects.create(year=2026, month=9, item='ضيافة', amount=Decimal('2.00'))
        self.client.force_login(self.admin)
        page = self.client.get(reverse('reset_data'))
        row = next(item for item in page.context['counts'] if item['key'] == 'social_committee')
        self.assertEqual(row['count'], 2)
        self.client.post(reverse('reset_data'), {'action': 'flush_one', 'key': 'social_committee', 'confirm': 'YES'})
        self.assertFalse(SocialCommitteePayment.objects.exists())
        self.assertFalse(SocialCommitteeExpense.objects.exists())
        self.assertEqual(Teacher.objects.count(), 2)
