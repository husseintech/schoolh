from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Class, Subject
from .teacher_records_models import ClassSubjectMapping


@login_required
def class_subject_mapping(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'هذه الصفحة مخصصة للإدارة')
        return redirect('dashboard')

    classes = Class.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    selected_class = None
    selected_ids = []
    class_id = request.GET.get('class_id') or request.POST.get('class_id')

    if class_id:
        selected_class = get_object_or_404(Class, pk=class_id)
        selected_ids = list(ClassSubjectMapping.objects.filter(student_class=selected_class).values_list('subject_id', flat=True))

    if request.method == 'POST' and selected_class:
        requested_ids = {int(v) for v in request.POST.getlist('subjects') if str(v).isdigit()}
        valid_ids = set(Subject.objects.filter(id__in=requested_ids).values_list('id', flat=True))
        existing_ids = set(ClassSubjectMapping.objects.filter(student_class=selected_class).values_list('subject_id', flat=True))

        to_delete = existing_ids - valid_ids
        if to_delete:
            ClassSubjectMapping.objects.filter(student_class=selected_class, subject_id__in=to_delete).delete()

        for subject_id in valid_ids - existing_ids:
            ClassSubjectMapping.objects.create(
                student_class=selected_class,
                subject_id=subject_id,
                created_by=request.user,
            )

        messages.success(request, f'تم حفظ المواد المخصصة للصف {selected_class.name}')
        return redirect(f'/administration/teacher-records/class-subjects/?class_id={selected_class.id}')

    mapping_summary = []
    for student_class in classes:
        mapped = Subject.objects.filter(class_mappings__student_class=student_class).distinct().order_by('name')
        mapping_summary.append({'student_class': student_class, 'subjects': mapped})

    return render(request, 'school/class_subject_mapping.html', {
        'classes': classes,
        'subjects': subjects,
        'selected_class': selected_class,
        'selected_ids': selected_ids,
        'mapping_summary': mapping_summary,
    })
