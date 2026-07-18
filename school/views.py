import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from dotenv import set_key
from .models import Profile, Student, Note
from .forms import StudentForm, NoteForm, StudentEditForm
from .services import send_whatsapp_message


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة')
    return render(request, 'school/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    profile = request.user.profile
    if profile.role == 'admin':
        students_count = Student.objects.count()
        notes_count = Note.objects.count()
        return render(request, 'school/admin_dashboard.html', {
            'students_count': students_count,
            'notes_count': notes_count,
        })
    elif profile.role == 'teacher':
        students = Student.objects.all()
        return render(request, 'school/teacher_dashboard.html', {
            'students': students,
        })
    else:
        try:
            student = request.user.student_profile
            notes = student.notes.all().order_by('-created_at')
            notes.update(is_read=True)
            return render(request, 'school/student_dashboard.html', {
                'student': student,
                'notes': notes,
            })
        except Student.DoesNotExist:
            messages.error(request, 'لا يوجد ملف طالب مرتبط بهذا الحساب')
            return redirect('logout')


@login_required
def add_student(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة الطالب بنجاح')
            return redirect('student_list')
    else:
        form = StudentForm()
    return render(request, 'school/add_student.html', {'form': form})


@login_required
def student_list(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    students = Student.objects.all().order_by('class_name', 'full_name')
    return render(request, 'school/student_list.html', {'students': students})


@login_required
def edit_student(request, student_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        form = StudentEditForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات الطالب بنجاح')
            return redirect('student_list')
    else:
        form = StudentEditForm(instance=student)
    return render(request, 'school/edit_student.html', {'form': form, 'student': student})


@login_required
def delete_student(request, student_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        user = student.user
        student.delete()
        user.delete()
        messages.success(request, 'تم حذف الطالب بنجاح')
        return redirect('student_list')
    return render(request, 'school/delete_student.html', {'student': student})


@login_required
def add_note(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = NoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.created_by = request.user
            note.save()
            student = note.student
            if student.parent_phone:
                note_type = note.get_note_type_display()
                msg = f'السلام عليكم، طالبكم {student.full_name}\nنوع الملاحظة: {note_type}\nالتفاصيل: {note.content}'
                sent = send_whatsapp_message(student.parent_phone, msg)
                if sent:
                    messages.success(request, 'تم إضافة الملاحظة بنجاح وتم إرسال إشعار واتساب لولي الأمر')
                else:
                    messages.warning(request, 'تم إضافة الملاحظة ولكن تعذر إرسال رسالة واتساب')
            else:
                messages.success(request, 'تم إضافة الملاحظة بنجاح (لا يوجد رقم هاتف مسجل لولي الأمر)')
            return redirect('note_list')
    else:
        form = NoteForm()
        if request.user.profile.role == 'teacher':
            form.fields['student'].queryset = Student.objects.all()
    return render(request, 'school/add_note.html', {'form': form})


@login_required
def note_list(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.user.profile.role == 'admin':
        notes = Note.objects.all().select_related('student', 'created_by').order_by('-created_at')
    else:
        notes = Note.objects.filter(created_by=request.user).select_related('student').order_by('-created_at')
    return render(request, 'school/note_list.html', {'notes': notes})


@login_required
def student_notes(request, student_id):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    student = get_object_or_404(Student, id=student_id)
    notes = Note.objects.filter(student=student).select_related('created_by').order_by('-created_at')
    return render(request, 'school/student_notes.html', {'student': student, 'notes': notes})


@login_required
def whatsapp_settings(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    env_path = settings.BASE_DIR / '.env'
    if request.method == 'POST':
        provider = request.POST.get('provider', 'log')
        token = request.POST.get('ultramsg_token', '')
        instance_id = request.POST.get('ultramsg_instance_id', '')
        set_key(str(env_path), 'WHATSAPP_PROVIDER', provider)
        set_key(str(env_path), 'ULTRAMSG_TOKEN', token)
        set_key(str(env_path), 'ULTRAMSG_INSTANCE_ID', instance_id)
        os.environ['WHATSAPP_PROVIDER'] = provider
        os.environ['ULTRAMSG_TOKEN'] = token
        os.environ['ULTRAMSG_INSTANCE_ID'] = instance_id
        messages.success(request, 'تم حفظ إعدادات واتساب بنجاح')
        return redirect('dashboard')
    context = {
        'current_provider': os.getenv('WHATSAPP_PROVIDER', 'log'),
        'ultramsg_token': os.getenv('ULTRAMSG_TOKEN', ''),
        'ultramsg_instance_id': os.getenv('ULTRAMSG_INSTANCE_ID', ''),
    }
    return render(request, 'school/whatsapp_settings.html', context)
