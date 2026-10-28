from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def kindergarten_visit_form(request, teacher_id, report_id=None):
    # Feature intentionally disabled; keep the named route to avoid breaking
    # reverse URL resolution while rendering the standard visit-program page.
    messages.info(request, 'تم إيقاف ميزة تقارير زيارات التمهيدي. برنامج الزيارات العادي ما زال متاحًا.')
    return redirect('visit_program_list')


@login_required
def kindergarten_visit_edit(request, teacher_id, report_id):
    return kindergarten_visit_form(request, teacher_id, report_id)
