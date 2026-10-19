from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import LabRegisterEntry, LibraryLoan, has_perm

def can(user, action): return has_perm(user, "registers", action)
def deny(request):
    messages.error(request, "ليس لديك صلاحية للوصول إلى هذه الصفحة")
    return redirect("dashboard")
def cutoff(): return timezone.localdate() - timedelta(days=15)

@login_required
def registers_home(request):
    if not can(request.user,"view"): return deny(request)
    loans=LibraryLoan.objects.all()
    return render(request,"school/registers_home.html",{"active_loans":loans.filter(returned_date__isnull=True).count(),"returned_loans":loans.filter(returned_date__isnull=False).count(),"overdue_loans":loans.filter(returned_date__isnull=True,loan_date__lt=cutoff()).count(),"science_count":LabRegisterEntry.objects.filter(register_type="science").count(),"computer_count":LabRegisterEntry.objects.filter(register_type="computer").count()})

@login_required
def library_register(request):
    if not can(request.user,"view"): return deny(request)
    q=(request.GET.get("q") or "").strip()
    loans=LibraryLoan.objects.all()
    if q: loans=loans.filter(Q(borrower_name__icontains=q)|Q(book_title__icontains=q)|Q(classification_number__icontains=q))
    today=timezone.localdate()
    active=loans.filter(returned_date__isnull=True).order_by("loan_date","borrower_name")
    returned=loans.filter(returned_date__isnull=False).order_by("-returned_date","borrower_name")
    overdue=active.filter(loan_date__lt=cutoff())
    if request.method=="POST":
        if not can(request.user,"add"): return deny(request)
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
    if not can(request.user,"edit"): return deny(request)
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
    if not can(request.user,"delete"): return deny(request)
    get_object_or_404(LibraryLoan,pk=loan_id).delete()
    messages.success(request,"تم حذف سجل الإعارة.")
    return redirect("library_register")

@login_required
def lab_register(request,register_type):
    if register_type not in ("science","computer"): return redirect("registers_home")
    if not can(request.user,"view"): return deny(request)
    records=LabRegisterEntry.objects.filter(register_type=register_type)
    q=(request.GET.get("q") or "").strip()
    if q: records=records.filter(Q(title__icontains=q)|Q(details__icontains=q)|Q(notes__icontains=q))
    if request.method=="POST":
        if not can(request.user,"add"): return deny(request)
        title=(request.POST.get("title") or "").strip()
        try:
            entry_date=date.fromisoformat(request.POST.get("entry_date") or timezone.localdate().isoformat())
            if entry_date>timezone.localdate(): raise ValueError
        except ValueError: messages.error(request,"التاريخ غير صحيح.")
        else:
            if not title: messages.error(request,"يرجى إدخال عنوان البيان.")
            else:
                LabRegisterEntry.objects.create(register_type=register_type,entry_date=entry_date,title=title,details=(request.POST.get("details") or "").strip(),notes=(request.POST.get("notes") or "").strip(),created_by=request.user)
                messages.success(request,"تم حفظ البيان.")
                return redirect("lab_register",register_type=register_type)
    return render(request,"school/lab_register.html",{"records":records,"q":q,"register_type":register_type,"register_title":"سجل مختبر العلوم" if register_type=="science" else "سجل مختبر الحاسوب","can_add":can(request.user,"add"),"can_delete":can(request.user,"delete")})

@login_required
@require_POST
def lab_register_delete(request,entry_id):
    if not can(request.user,"delete"): return deny(request)
    entry=get_object_or_404(LabRegisterEntry,pk=entry_id)
    kind=entry.register_type; entry.delete()
    messages.success(request,"تم حذف البيان.")
    return redirect("lab_register",register_type=kind)

@login_required
def library_report(request,report_type):
    if not can(request.user,"print"): return deny(request)
    today=timezone.localdate(); loans=LibraryLoan.objects.all()
    titles={"active":"تقرير الكتب المعارة","returned":"تقرير الكتب المعادة","overdue":"تقرير الكتب المتأخرة"}
    if report_type=="active": loans=loans.filter(returned_date__isnull=True)
    elif report_type=="returned": loans=loans.filter(returned_date__isnull=False)
    elif report_type=="overdue": loans=loans.filter(returned_date__isnull=True,loan_date__lt=cutoff())
    else: return redirect("library_register")
    return render(request,"school/library_report_print.html",{"loans":loans.order_by("loan_date","borrower_name"),"report_title":titles[report_type],"report_type":report_type,"today":today})
