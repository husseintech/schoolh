from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import Class, SchoolInfo, Subject


def _to_int(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _percentage(passed, total):
    if total <= 0:
        return Decimal('0.00')
    try:
        return (Decimal(passed) * Decimal('100') / Decimal(total)).quantize(Decimal('0.01'))
    except (InvalidOperation, ZeroDivisionError):
        return Decimal('0.00')


@login_required
def academic_achievement_report(request):
    """Admin-only printable report based on the official Word achievement-analysis form."""
    if request.user.profile.role != 'admin':
        messages.error(request, 'هذا التقرير مخصص للإدارة')
        return redirect('dashboard')

    classes = Class.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    selected_class = None
    total_students = 0

    class_id = request.GET.get('class_id') or request.POST.get('class_id')
    if class_id:
        try:
            selected_class = Class.objects.get(pk=class_id)
            total_students = selected_class.students.count()
        except (Class.DoesNotExist, ValueError):
            selected_class = None

    if request.method == 'POST':
        if not selected_class:
            messages.error(request, 'يرجى اختيار الصف/الشعبة')
            return redirect('academic_achievement_report')

        rows = []
        for subject in subjects:
            half_passed = _to_int(request.POST.get(f'half_passed_{subject.id}'))
            half_failed = _to_int(request.POST.get(f'half_failed_{subject.id}'))
            final_passed = _to_int(request.POST.get(f'final_passed_{subject.id}'))
            final_failed = _to_int(request.POST.get(f'final_failed_{subject.id}'))

            # Keep entered counts realistic for the selected class.
            if half_passed + half_failed > total_students or final_passed + final_failed > total_students:
                messages.error(request, f'مجموع الناجحين والراسبين في مبحث {subject.name} أكبر من عدد طلبة الصف')
                return render(request, 'school/academic_achievement_form.html', {
                    'classes': classes,
                    'subjects': subjects,
                    'selected_class': selected_class,
                    'total_students': total_students,
                    'school_year': request.POST.get('school_year', ''),
                    'semester': request.POST.get('semester', ''),
                })

            half_percentage = _percentage(half_passed, total_students)
            final_percentage = _percentage(final_passed, total_students)
            rows.append({
                'subject': subject,
                'half_passed': half_passed,
                'half_failed': half_failed,
                'half_percentage': half_percentage,
                'final_passed': final_passed,
                'final_failed': final_failed,
                'final_percentage': final_percentage,
                'percentage_difference': final_percentage - half_percentage,
                'recommendation': request.POST.get(f'recommendation_{subject.id}', '').strip(),
            })

        return render(request, 'school/academic_achievement_print.html', {
            'info': SchoolInfo.objects.first(),
            'selected_class': selected_class,
            'total_students': total_students,
            'school_year': request.POST.get('school_year', '').strip(),
            'semester': request.POST.get('semester', '').strip(),
            'rows': rows,
        })

    return render(request, 'school/academic_achievement_form.html', {
        'classes': classes,
        'subjects': subjects,
        'selected_class': selected_class,
        'total_students': total_students,
    })
