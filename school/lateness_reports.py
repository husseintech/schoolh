from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.contrib import messages

from .models import Student, has_perm


@login_required
def lateness_summary_report(request):
    """Compact per-student lateness summary and a separate list for students late more than three times."""
    if not has_perm(request.user, 'lateness', 'view'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')

    today = date.today()
    current_year = today.year
    month = request.GET.get('month', str(today.month))
    if month not in {str(i) for i in range(1, 13)}:
        month = ''

    lateness_filter = Q(lateness__date__year=current_year)
    if month:
        lateness_filter &= Q(lateness__date__month=int(month))

    students = (
        Student.objects.select_related('student_class')
        .annotate(lateness_count=Count('lateness', filter=lateness_filter))
        .filter(lateness_count__gt=0)
        .order_by('-lateness_count', 'student_class__name', 'full_name')
    )
    frequent_students = students.filter(lateness_count__gt=3)

    months = [
        ('1', 'يناير'), ('2', 'فبراير'), ('3', 'مارس'), ('4', 'إبريل'),
        ('5', 'مايو'), ('6', 'يونيو'), ('7', 'يوليو'), ('8', 'أغسطس'),
        ('9', 'سبتمبر'), ('10', 'أكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
    ]
    return render(request, 'school/lateness_summary_report.html', {
        'students_with_lateness': students,
        'frequent_students': frequent_students,
        'months': months,
        'selected_month': month,
        'current_year': current_year,
    })
