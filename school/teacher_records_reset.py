from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from .teacher_records_models import CurriculumProgressRecord, TeacherTrainingRecord


@login_required
def teacher_records_reset(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    tables = [('curriculum','سجل متابعة ما قطع من المنهاج',CurriculumProgressRecord),('training','سجل الدورات',TeacherTrainingRecord)]
    if request.method == 'POST' and request.POST.get('confirm') == 'YES':
        key=request.POST.get('key')
        for k,label,model in tables:
            if k==key:
                count=model.objects.count(); model.objects.all().delete(); messages.success(request,f'تم تفريغ {label} ({count} سجل)'); break
        return redirect('teacher_records_reset')
    return render(request,'school/teacher_records_reset.html',{'counts':[{'key':k,'label':l,'count':m.objects.count()} for k,l,m in tables]})
