from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Class, LabRegisterEntry, LibraryLoan, has_perm

def can(user, action, module="registers"): return has_perm(user, module, action)

def register_module(register_type):
    return "science_lab_register" if register_type == "science" else "computer_lab_register"
def deny(request):
    messages.error(request, "ليس لديك صلاحية للوصول إلى هذه الصفحة")
    return redirect("dashboard")
def cutoff(): return timezone.localdate() - timedelta(days=15)

@login_required
def registers_home(request):
    if not any(can(request.user, "view", module) for module in ("library_register", "science_lab_register", "computer_lab_register")):
        return deny(request)
    loans=LibraryLoan.objects.all()
    return render(request,"school/registers_home.html",{"active_loans":loans.filter(returned_date__isnull=True).count(),"returned_loans":loans.filter(returned_date__isnull=False).count(),"overdue_loans":loans.filter(returned_date__isnull=True,loan_date__lt=cutoff()).count(),"science_count":LabRegisterEntry.objects.filter(register_type="science").count(),"computer_count":LabRegisterEntry.objects.filter(register_type="computer").count(), "can_library":can(request.user,"view","library_register"), "can_science":can(request.user,"view","science_lab_register"), "can_computer":can(request.user,"view","computer_lab_register")})

@login_required
def library_register(request):
    if not can(request.user,"view","library_register"): return deny(request)
    q=(request.GET.get("q") or "").strip()
    loans=LibraryLoan.objects.all()
    if q: loans=loans.filter(Q(borrower_name__icontains=q)|Q(book_title__icontains=q)|Q(classification_number__icontains=q))
    today=timezone.localdate()
    active=loans.filter(returned_date__isnull=True).order_by("loan_date","borrower_name")
    returned=loans.filter(returned_date__isnull=False).order_by("-returned_date","borrower_name")
    overdue=active.filter(loan_date__lt=cutoff())
    if request.method=="POST":
        if not can(request.user,"add","library_register"): return deny(request)
        borrower=(request.POST.get("borrower_name") or "").strip()
        title=(request.POST.get("book_title") or "").strip()
        try:
            loan_date=date.fromisoformat(request.POST.get("loan_date") or today.isoformat())
            due_date=date.fromisoformat(request.POST["due_date"]) if request.POST.get("due_date") else None
            if loan_date>today or (due_date and due_date<loan_date): raise ValueError
        except ValueError: messages.error(request,"يرجى التأكد من صحة التواريخ.")
        else:
            if not borrower or not title: messages.error(request,"يرجى إدخال اسم المستعير واسم الكتاب.")
            else:
                LibraryLoan.objects.create(borrower_name=borrower,book_title=title,classification_number=(request.POST.get("classification_number") or "").strip(),loan_date=loan_date,due_date=due_date,notes=(request.POST.get("notes") or "").strip(),created_by=request.user)
                messages.success(request,"تم تسجيل إعارة الكتاب.")
                return redirect("library_register")
    return render(request,"school/library_register.html",{"active_loans":active,"returned_loans":returned,"overdue_loans":overdue,"active_count":active.count(),"returned_count":returned.count(),"overdue_count":overdue.count(),"q":q,"today":today})

@login_required
@require_POST
def library_return(request,loan_id):
    if not can(request.user,"edit","library_register"): return deny(request)
    loan=get_object_or_404(LibraryLoan,pk=loan_id)
    if loan.returned_date is None:
        try:
            returned=date.fromisoformat(request.POST.get("returned_date") or timezone.localdate().isoformat())
            if returned<loan.loan_date or returned>timezone.localdate(): raise ValueError
        except ValueError: messages.error(request,"تاريخ الإعادة غير صحيح.")
        else:
            loan.returned_date=returned
            loan.save(update_fields=["returned_date","updated_at"])
            messages.success(request,"تم تسجيل إعادة الكتاب.")
    return redirect("library_register")

@login_required
@require_POST
def library_delete(request,loan_id):
    if not can(request.user,"delete","library_register"): return deny(request)
    get_object_or_404(LibraryLoan,pk=loan_id).delete()
    messages.success(request,"تم حذف سجل الإعارة.")
    return redirect("library_register")

@login_required
def lab_register(request,register_type):
    if register_type not in ("science","computer"): return redirect("registers_home")
    module = register_module(register_type)
    if not can(request.user,"view",module): return deny(request)
    records=LabRegisterEntry.objects.filter(register_type=register_type)
    q=(request.GET.get("q") or "").strip()
    classes=Class.objects.all().order_by("name")
    if q: records=records.filter(Q(title__icontains=q)|Q(session_title__icontains=q)|Q(grade__icontains=q)|Q(teacher_name__icontains=q)|Q(programs_used__icontains=q)|Q(objectives_activities__icontains=q)|Q(details__icontains=q)|Q(notes__icontains=q)|Q(activity_number__icontains=q)|Q(unit_lesson__icontains=q)|Q(learning_outcomes__icontains=q)|Q(tools_materials__icontains=q)|Q(actual_observations__icontains=q))
    if request.method=="POST":
        if not can(request.user,"add",module): return deny(request)
        title=(request.POST.get("title") or request.POST.get("session_title") or "").strip()
        try:
            entry_date=date.fromisoformat(request.POST.get("entry_date") or timezone.localdate().isoformat())
            if entry_date>timezone.localdate(): raise ValueError
        except ValueError: messages.error(request,"التاريخ غير صحيح.")
        else:
            if not title: messages.error(request,"يرجى إدخال عنوان البيان.")
            else:
                session_title=(request.POST.get("session_title") or title).strip()
                programs_used=(request.POST.get("programs_used") or "").strip()
                objectives_activities=(request.POST.get("objectives_activities") or request.POST.get("details") or "").strip()
                teacher_name=(request.POST.get("teacher_name") or "").strip()
                notes=(request.POST.get("notes") or "").strip()
                lab_supervisor_notes=(request.POST.get("lab_supervisor_notes") or "").strip()
                director_notes=(request.POST.get("director_notes") or "").strip()
                extra={}
                if register_type=="science":
                    raw_count=(request.POST.get("student_count") or "").strip()
                    try:
                        student_count=int(raw_count) if raw_count else None
                        if student_count is not None and student_count < 0: raise ValueError
                    except ValueError:
                        messages.error(request,"عدد الطلبة غير صحيح.")
                        return redirect("lab_register",register_type=register_type)
                    steps="\n".join(f"{n}) {(request.POST.get('step_'+str(n)) or '').strip()}" for n in (1,2,3) if (request.POST.get('step_'+str(n)) or '').strip())
                    extra={
                        "activity_number":(request.POST.get("activity_number") or "").strip(),
                        "semester":(request.POST.get("semester") or "").strip(),
                        "section":(request.POST.get("section") or "").strip(),
                        "student_count":student_count,
                        "unit_lesson":(request.POST.get("unit_lesson") or "").strip(),
                        "learning_outcomes":(request.POST.get("learning_outcomes") or "").strip(),
                        "tools_materials":(request.POST.get("tools_materials") or "").strip(),
                        "safety_procedures":(request.POST.get("safety_procedures") or "").strip(),
                        "implementation_steps":steps,
                        "actual_observations":(request.POST.get("actual_observations") or "").strip(),
                        "results_conclusion":(request.POST.get("results_conclusion") or "").strip(),
                        "assessment":(request.POST.get("assessment") or "").strip(),
                        "incidents_actions":(request.POST.get("incidents_actions") or "").strip(),
                        "followup_activity":(request.POST.get("followup_activity") or "").strip(),
                    }
                LabRegisterEntry.objects.create(
                    register_type=register_type, entry_date=entry_date,
                    day=(request.POST.get("day") or "").strip(),
                    grade=(request.POST.get("grade") or "").strip(),
                    title=title, session_title=session_title,
                    programs_used=programs_used, objectives_activities=objectives_activities,
                    teacher_name=teacher_name, details=(request.POST.get("details") or objectives_activities).strip(),
                    notes=notes, lab_supervisor_notes=lab_supervisor_notes,
                    director_notes=director_notes, created_by=request.user, **extra
                )
                messages.success(request,"تم حفظ البيان.")
                return redirect("lab_register",register_type=register_type)
    return render(request,"school/lab_register.html",{"records":records,"q":q,"register_type":register_type,"register_title":"سجل مختبر العلوم" if register_type=="science" else "سجل مختبر الحاسوب","can_add":can(request.user,"add",module),"can_delete":can(request.user,"delete",module),"classes":classes,"today":timezone.localdate()})

@login_required
@require_POST
def lab_register_delete(request,entry_id):
    entry=get_object_or_404(LabRegisterEntry,pk=entry_id)
    if not can(request.user,"delete",register_module(entry.register_type)): return deny(request)
    kind=entry.register_type; entry.delete()
    messages.success(request,"تم حذف البيان.")
    return redirect("lab_register",register_type=kind)

@login_required
def library_report(request,report_type):
    if not can(request.user,"print","library_register"): return deny(request)
    today=timezone.localdate(); loans=LibraryLoan.objects.all()
    titles={"active":"تقرير الكتب المعارة","returned":"تقرير الكتب المعادة","overdue":"تقرير الكتب المتأخرة"}
    if report_type=="active": loans=loans.filter(returned_date__isnull=True)
    elif report_type=="returned": loans=loans.filter(returned_date__isnull=False)
    elif report_type=="overdue": loans=loans.filter(returned_date__isnull=True,loan_date__lt=cutoff())
    else: return redirect("library_register")
    return render(request,"school/library_report_print.html",{"loans":loans.order_by("loan_date","borrower_name"),"report_title":titles[report_type],"report_type":report_type,"today":today})
