from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import (
    AuditLog, SchoolInfo, SocialCommitteeExpense, SocialCommitteePayment,
    Teacher, has_perm,
)

ZERO = Decimal('0.00')
MAX_AMOUNT = Decimal('99999999.99')


def _period(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year') or request.POST.get('year') or today.year)
        month = int(request.GET.get('month') or request.POST.get('month') or today.month)
    except (TypeError, ValueError):
        return None
    return (year, month) if 2000 <= year <= 2100 and 1 <= month <= 12 else None


def _amount(raw, *, positive=False):
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise ValueError('أدخل مبلغًا رقميًا صالحًا')
    if not value.is_finite() or value > MAX_AMOUNT or value < (Decimal('0.01') if positive else ZERO):
        raise ValueError('المبلغ يجب أن يكون موجبًا وضمن الحد المسموح' if positive else 'المبلغ يجب ألا يكون سالبًا')
    if value.as_tuple().exponent < -2 and value != value.quantize(Decimal('0.01')):
        raise ValueError('استخدم منزلتين عشريتين كحد أقصى')
    return value.quantize(Decimal('0.01'))


def _period_url(year, month):
    return f"{reverse('social_committee')}?year={year}&month={month}"


def _audit(user, action, details):
    AuditLog.objects.create(user=user, user_role=user.profile.role, action=action, details=details)


def _monthly_data(year, month, teachers=None):
    teachers = teachers if teachers is not None else list(Teacher.objects.order_by('full_name'))
    payments = list(SocialCommitteePayment.objects.filter(year=year, month=month).select_related('teacher'))
    expenses = list(SocialCommitteeExpense.objects.filter(year=year, month=month).order_by('id'))
    payment_map = {payment.teacher_id: payment for payment in payments if payment.teacher_id}
    rows = [
        {'teacher': teacher, 'payment': payment_map.get(teacher.id), 'archived_name': '',
         'amount': payment_map[teacher.id].amount if teacher.id in payment_map else ZERO}
        for teacher in teachers
    ]
    current_ids = {teacher.id for teacher in teachers}
    archived_payments = [payment for payment in payments if payment.teacher_id not in current_ids]
    paid = [row for row in rows if row['amount'] > ZERO]
    paid.extend({'teacher': None, 'payment': payment, 'amount': payment.amount,
                 'archived_name': payment.teacher_name} for payment in archived_payments if payment.amount > ZERO)
    income = sum((payment.amount for payment in payments), ZERO)
    spending = sum((expense.amount for expense in expenses), ZERO)
    balance = income - spending
    return {
        'year': year, 'month': month, 'rows': rows, 'paid': paid,
        'unpaid': [row for row in rows if row['amount'] <= ZERO],
        'expenses': expenses, 'income': income, 'spending': spending,
        'archived_payments': archived_payments,
        'balance': balance, 'surplus': max(balance, ZERO), 'deficit': max(-balance, ZERO),
    }


@login_required
def social_committee(request):
    if not has_perm(request.user, 'social_committee', 'view'):
        messages.error(request, 'ليس لديك صلاحية لعرض اللجنة الاجتماعية')
        return redirect('dashboard')
    period = _period(request)
    if not period:
        messages.error(request, 'اختر سنة وشهرًا صالحين')
        return redirect('social_committee')
    year, month = period
    teachers = list(Teacher.objects.order_by('full_name'))

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_payments':
            existing = {p.teacher_id: p for p in SocialCommitteePayment.objects.filter(
                year=year, month=month, teacher__in=teachers,
            )}
            changes = []
            try:
                for teacher in teachers:
                    if f'amount_{teacher.id}' not in request.POST and f'notes_{teacher.id}' not in request.POST:
                        continue
                    raw = request.POST.get(f'amount_{teacher.id}', '').strip()
                    old = existing.get(teacher.id)
                    notes = request.POST.get(f'notes_{teacher.id}', old.notes if old else '').strip()
                    if len(notes) > 500:
                        raise ValueError('الملاحظات طويلة جدًا')
                    amount = _amount(raw) if raw else (old.amount if old else ZERO)
                    if old and old.amount == amount and old.notes == notes:
                        continue
                    if not old and amount == ZERO and not notes:
                        continue
                    required = 'edit' if old else 'add'
                    if not has_perm(request.user, 'social_committee', required):
                        raise ValueError('ليس لديك صلاحية لإضافة أو تعديل مدفوعات المعلمين')
                    changes.append((teacher, old, amount, notes))
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect(_period_url(year, month))
            with transaction.atomic():
                for teacher, old, amount, notes in changes:
                    if old:
                        old.amount, old.notes, old.teacher_name = amount, notes, teacher.full_name
                        old.save(update_fields=['amount', 'notes', 'teacher_name', 'updated_at'])
                    else:
                        SocialCommitteePayment.objects.create(
                            teacher=teacher, teacher_name=teacher.full_name,
                            year=year, month=month, amount=amount, notes=notes,
                        )
                if changes:
                    _audit(request.user, 'تحديث مدفوعات اللجنة الاجتماعية', f'{year}/{month}: {len(changes)} معلم')
            messages.success(request, 'تم حفظ مدفوعات المعلمين')
        elif action == 'add_expense':
            if not has_perm(request.user, 'social_committee', 'add'):
                messages.error(request, 'ليس لديك صلاحية لإضافة المشتريات')
                return redirect(_period_url(year, month))
            item = request.POST.get('item', '').strip()
            notes = request.POST.get('notes', '').strip()
            try:
                if not item or len(item) > 200 or len(notes) > 500:
                    raise ValueError('أدخل بند مشتريات وملاحظات بطول صالح')
                amount = _amount(request.POST.get('amount'), positive=True)
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect(_period_url(year, month))
            with transaction.atomic():
                SocialCommitteeExpense.objects.create(year=year, month=month, item=item,
                                                      amount=amount, notes=notes, created_by=request.user)
                _audit(request.user, 'إضافة مشتريات اللجنة الاجتماعية', f'{year}/{month}: {item} - {amount}')
            messages.success(request, 'تمت إضافة بند المشتريات')
        else:
            messages.error(request, 'طلب غير معروف')
        return redirect(_period_url(year, month))

    month_data = _monthly_data(year, month, teachers)
    annual = [_monthly_data(year, number, teachers) for number in range(1, 13)]
    annual_income = sum((data['income'] for data in annual), ZERO)
    annual_spending = sum((data['spending'] for data in annual), ZERO)
    annual_balance = annual_income - annual_spending
    return render(request, 'school/social_committee.html', {
        **month_data,
        'months': range(1, 13), 'annual_income': annual_income,
        'annual_spending': annual_spending, 'annual_balance': annual_balance,
        'annual_surplus': max(annual_balance, ZERO), 'annual_deficit': max(-annual_balance, ZERO),
        'can_add': has_perm(request.user, 'social_committee', 'add'),
        'can_edit': has_perm(request.user, 'social_committee', 'edit'),
        'can_delete': has_perm(request.user, 'social_committee', 'delete'),
        'can_print': has_perm(request.user, 'social_committee', 'print'),
    })


@login_required
def social_committee_expense(request, expense_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not has_perm(request.user, 'social_committee', 'view'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    expense = get_object_or_404(SocialCommitteeExpense, pk=expense_id)
    url = _period_url(expense.year, expense.month)
    action = request.POST.get('action')
    if action == 'delete':
        if not has_perm(request.user, 'social_committee', 'delete'):
            messages.error(request, 'ليس لديك صلاحية للحذف')
            return redirect(url)
        with transaction.atomic():
            _audit(request.user, 'حذف مشتريات اللجنة الاجتماعية', f'{expense.year}/{expense.month}: {expense.item} - {expense.amount}')
            expense.delete()
        messages.success(request, 'تم حذف بند المشتريات')
    elif action == 'edit':
        if not has_perm(request.user, 'social_committee', 'edit'):
            messages.error(request, 'ليس لديك صلاحية للتعديل')
            return redirect(url)
        item = request.POST.get('item', '').strip()
        notes = request.POST.get('notes', '').strip()
        try:
            if not item or len(item) > 200 or len(notes) > 500:
                raise ValueError('أدخل بند مشتريات وملاحظات بطول صالح')
            amount = _amount(request.POST.get('amount'), positive=True)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(url)
        with transaction.atomic():
            expense.item, expense.amount, expense.notes = item, amount, notes
            expense.save(update_fields=['item', 'amount', 'notes'])
            _audit(request.user, 'تعديل مشتريات اللجنة الاجتماعية', f'{expense.year}/{expense.month}: {item} - {amount}')
        messages.success(request, 'تم تعديل بند المشتريات')
    else:
        messages.error(request, 'طلب غير معروف')
    return redirect(url)


@login_required
def social_committee_report(request):
    if not (has_perm(request.user, 'social_committee', 'view')
            and has_perm(request.user, 'social_committee', 'print')):
        messages.error(request, 'ليس لديك صلاحية لطباعة تقارير اللجنة الاجتماعية')
        return redirect('dashboard')
    period = _period(request)
    kind = request.GET.get('kind', 'monthly')
    report_type = request.GET.get('report_type', 'paid')
    if report_type not in ('monthly', 'paid', 'unpaid', 'expenses'):
        report_type = 'paid'
    if kind == 'multi':
        kind = 'multi'
    if not period or kind not in ('monthly', 'paid', 'unpaid', 'expenses', 'annual', 'annual_unpaid', 'multi'):
        messages.error(request, 'اختر تقريرًا وفترة صالحين')
        return redirect('social_committee')
    year, month = period
    teachers = list(Teacher.objects.order_by('full_name'))

    selected_months = []
    for raw_month in request.GET.getlist('months'):
        try:
            number = int(raw_month)
        except (TypeError, ValueError):
            continue
        if 1 <= number <= 12 and number not in selected_months:
            selected_months.append(number)
    selected_months.sort()

    multi_data = [_monthly_data(year, number, teachers) for number in selected_months] if kind == 'multi' else []
    multi_report_type = report_type if kind == 'multi' else ''
    multi_paid = []
    multi_unpaid = []
    multi_expenses = []
    for month_data in multi_data:
        for row in month_data['paid']:
            multi_paid.append({**row, 'month': month_data['month']})
        for row in month_data['unpaid']:
            multi_unpaid.append({**row, 'month': month_data['month']})
        for expense in month_data['expenses']:
            multi_expenses.append({'expense': expense, 'month': month_data['month']})

    if kind == 'multi' and not selected_months:
        messages.error(request, 'اختر شهرًا واحدًا على الأقل للتقرير')
        return redirect(_period_url(year, month))

    data = _monthly_data(year, month, teachers)
    annual = [_monthly_data(year, number, teachers) for number in range(1, 13)] if kind == 'annual' else []
    annual_unpaid_rows = []
    if kind == 'annual_unpaid':
        paid_pairs = set(
            SocialCommitteePayment.objects.filter(
                year=year, month__range=(1, 12), teacher__in=teachers, amount__gt=ZERO
            ).values_list('teacher_id', 'month')
        )
        for teacher in teachers:
            for month_number in range(1, 13):
                if (teacher.id, month_number) not in paid_pairs:
                    annual_unpaid_rows.append({'teacher': teacher, 'month': month_number})

    annual_income = sum((row['income'] for row in annual), ZERO)
    annual_spending = sum((row['spending'] for row in annual), ZERO)
    annual_balance = annual_income - annual_spending
    multi_income = sum((row['income'] for row in multi_data), ZERO)
    multi_spending = sum((row['spending'] for row in multi_data), ZERO)
    multi_balance = multi_income - multi_spending
    return render(request, 'school/social_committee_report.html', {
        **data, 'kind': kind, 'annual': annual,
        'annual_income': annual_income, 'annual_spending': annual_spending,
        'annual_balance': annual_balance,
        'annual_surplus': max(annual_balance, ZERO), 'annual_deficit': max(-annual_balance, ZERO),
        'selected_months': selected_months, 'multi_data': multi_data, 'multi_report_type': multi_report_type,
        'multi_paid': multi_paid, 'multi_unpaid': multi_unpaid, 'multi_expenses': multi_expenses,
        'multi_income': multi_income, 'multi_spending': multi_spending,
        'multi_balance': multi_balance, 'multi_surplus': max(multi_balance, ZERO),
        'multi_deficit': max(-multi_balance, ZERO),
        'info': SchoolInfo.objects.first(),
        'printed_at': timezone.localtime(),
    })
