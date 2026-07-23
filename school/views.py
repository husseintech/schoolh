import os, io, csv
from datetime import date, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from dotenv import set_key
from .models import Profile, Student, Note, Teacher, TeacherNote, Announcement, Agenda, StudentLeave, StudentLevel, ExamAnalysis, Message, Class, Subject
from .forms import (StudentForm, NoteForm, StudentEditForm, TeacherForm, TeacherEditForm,
    TeacherNoteForm, AnnouncementForm, AgendaForm, AgendaCompleteForm,
    StudentLeaveForm, StudentLevelForm, ExamAnalysisForm, MessageForm,
    ParentMessageForm, ClassForm, SubjectForm)
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
        return redirect('home')
    return redirect('home')


def logout_view(request):
    logout(request)
    return redirect('home')


def home(request):
    announcements = Announcement.objects.filter(is_active=True)[:5]
    return render(request, 'school/home.html', {'announcements': announcements})


@login_required
def dashboard(request):
    profile = request.user.profile
    if profile.role == 'admin':
        students_count = Student.objects.count()
        notes_count = Note.objects.count()
        teachers_count = Teacher.objects.count()
        unread_messages = Message.objects.filter(recipient__isnull=True, is_read=False).count()
        pending_agenda = Agenda.objects.filter(is_completed=False).count()
        return render(request, 'school/admin_dashboard.html', {
            'students_count': students_count,
            'notes_count': notes_count,
            'teachers_count': teachers_count,
            'unread_messages': unread_messages,
            'pending_agenda': pending_agenda,
        })
    elif profile.role == 'teacher':
        try:
            teacher = request.user.teacher_profile
            classes = teacher.classes.all()
            announcements = Announcement.objects.filter(is_active=True)[:5]
            return render(request, 'school/teacher_dashboard.html', {
                'teacher': teacher,
                'classes': classes,
                'announcements': announcements,
            })
        except Teacher.DoesNotExist:
            messages.error(request, 'لا يوجد ملف معلم مرتبط بهذا الحساب')
            return redirect('logout')
    else:
        try:
            student = request.user.student_profile
            notes = student.notes.filter(is_private=False).order_by('-created_at')
            notes.update(is_read=True)
            messages_qs = Message.objects.filter(recipient=request.user, is_read=False)
            return render(request, 'school/student_dashboard.html', {
                'student': student,
                'notes': notes,
                'unread_messages': messages_qs.count(),
            })
        except Student.DoesNotExist:
            messages.error(request, 'لا يوجد ملف طالب مرتبط بهذا الحساب')
            return redirect('logout')


# ─── Students ─────────────────────────────────────────────────────────────────

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
    user = request.user
    profile = user.profile

    if profile.role == 'admin':
        students = Student.objects.all().select_related('student_class').order_by('student_class__name', 'full_name')
    elif profile.role == 'teacher':
        try:
            teacher = user.teacher_profile
            classes = teacher.classes.all()
            students = Student.objects.filter(student_class__in=classes).select_related('student_class').order_by('student_class__name', 'full_name')
        except Teacher.DoesNotExist:
            students = Student.objects.none()
    else:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')

    classes = Class.objects.all().order_by('name')
    return render(request, 'school/student_list.html', {'students': students, 'classes': classes})


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
def student_notes(request, student_id):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    student = get_object_or_404(Student, id=student_id)
    user = request.user
    if user.profile.role == 'admin':
        notes = Note.objects.filter(student=student).select_related('created_by').order_by('-created_at')
    else:
        notes = Note.objects.filter(student=student, is_private=False).select_related('created_by').order_by('-created_at')
    return render(request, 'school/student_notes.html', {'student': student, 'notes': notes})


@login_required
def student_detail(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    notes = Note.objects.filter(student=student, is_private=False).select_related('created_by').order_by('-created_at')
    levels = StudentLevel.objects.filter(student=student).select_related('subject', 'created_by').order_by('-created_at')
    return render(request, 'school/student_detail.html', {
        'student': student,
        'notes': notes,
        'levels': levels,
    })


# ─── Excel Import/Export ──────────────────────────────────────────────────────

@login_required
def download_student_template(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'نموذج استيراد الطلاب'

    headers = ['الاسم الكامل', 'رقم الهوية', 'الصف', 'هاتف ولي الأمر', 'اسم ولي الأمر', 'العنوان', 'تاريخ الميلاد']
    ws.append(headers)

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = openpyxl.styles.Font(bold=True)
        cell.alignment = openpyxl.styles.Alignment(horizontal='center')

    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 20
    ws.column_dimensions['F'].width = 30
    ws.column_dimensions['G'].width = 15

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=نموذج_استيراد_الطلاب.xlsx'
    wb.save(response)
    return response


@login_required
def import_students(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')

    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, 'الرجاء رفع ملف Excel صالح (xlsx أو xls)')
            return redirect('student_list')

        import openpyxl
        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
        except Exception:
            messages.error(request, 'فشل في قراءة الملف. تأكد من أنه ملف Excel صالح.')
            return redirect('student_list')

        rows = list(ws.iter_rows(min_row=2, values_only=True))
        if not rows:
            messages.warning(request, 'الملف فارغ، لا توجد بيانات للاستيراد')
            return redirect('student_list')

        imported = 0
        errors = []
        for i, row in enumerate(rows, start=2):
            try:
                full_name = str(row[0]).strip() if row[0] else ''
                student_id = str(row[1]).strip() if row[1] else ''
                class_name = str(row[2]).strip() if row[2] else ''
                parent_phone = str(row[3]).strip() if row[3] else ''
                parent_name = str(row[4]).strip() if row[4] else ''
                address = str(row[5]).strip() if row[5] else ''
                birth_date = row[6]

                if not full_name or not student_id:
                    errors.append(f'الصف {i}: الاسم ورقم الهوية مطلوبان')
                    continue

                if Student.objects.filter(student_id=student_id).exists():
                    errors.append(f'الصف {i}: رقم الهوية {student_id} موجود مسبقاً')
                    continue

                class_obj = None
                if class_name:
                    class_obj, _ = Class.objects.get_or_create(name=class_name)

                if isinstance(birth_date, datetime):
                    bd = birth_date.date()
                elif isinstance(birth_date, date):
                    bd = birth_date
                else:
                    bd = None

                username = f'student_{student_id}'
                password = student_id[-6:] if len(student_id) >= 6 else student_id

                user = User.objects.create_user(username=username, password=password)
                Profile.objects.create(user=user, role='student')
                Student.objects.create(
                    user=user,
                    student_id=student_id,
                    full_name=full_name,
                    student_class=class_obj,
                    parent_phone=parent_phone,
                    parent_name=parent_name,
                    address=address,
                    birth_date=bd,
                )
                imported += 1
            except Exception as e:
                errors.append(f'الصف {i}: خطأ - {str(e)}')

        if imported:
            messages.success(request, f'تم استيراد {imported} طالب/طالب بنجاح')
        if errors:
            for err in errors[:10]:
                messages.warning(request, err)
            if len(errors) > 10:
                messages.warning(request, f'و {len(errors) - 10} خطأ آخر...')
        return redirect('student_list')

    return redirect('student_list')


@login_required
def export_students(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'الطلاب'

    headers = ['الاسم الكامل', 'رقم الهوية', 'الصف', 'هاتف ولي الأمر', 'اسم ولي الأمر', 'العنوان', 'تاريخ الميلاد']
    ws.append(headers)

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = openpyxl.styles.Font(bold=True)

    students = Student.objects.all().select_related('student_class').order_by('student_class__name', 'full_name')
    for s in students:
        ws.append([
            s.full_name,
            s.student_id,
            s.student_class.name if s.student_class else '',
            s.parent_phone,
            s.parent_name,
            s.address,
            s.birth_date.strftime('%Y-%m-%d') if s.birth_date else '',
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=قائمة_الطلاب.xlsx'
    wb.save(response)
    return response


# ─── Notes ────────────────────────────────────────────────────────────────────

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
            try:
                teacher = request.user.teacher_profile
                form.fields['student'].queryset = Student.objects.filter(student_class__in=teacher.classes.all())
            except Teacher.DoesNotExist:
                form.fields['student'].queryset = Student.objects.none()
    return render(request, 'school/add_note.html', {'form': form})


@login_required
def note_list(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.user.profile.role == 'admin':
        notes = Note.objects.all().select_related('student', 'created_by').order_by('-created_at')
    else:
        try:
            teacher = request.user.teacher_profile
            notes = Note.objects.filter(
                created_by=request.user
            ).select_related('student').order_by('-created_at')
        except Teacher.DoesNotExist:
            notes = Note.objects.none()
    return render(request, 'school/note_list.html', {'notes': notes})


# ─── Teachers ─────────────────────────────────────────────────────────────────

@login_required
def add_teacher(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة المعلم بنجاح')
            return redirect('teacher_list')
    else:
        form = TeacherForm()
    return render(request, 'school/add_teacher.html', {'form': form})


@login_required
def teacher_list(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    teachers = Teacher.objects.all().order_by('full_name')
    return render(request, 'school/teacher_list.html', {'teachers': teachers})


@login_required
def edit_teacher(request, teacher_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    teacher = get_object_or_404(Teacher, id=teacher_id)
    if request.method == 'POST':
        form = TeacherEditForm(request.POST, instance=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات المعلم بنجاح')
            return redirect('teacher_list')
    else:
        form = TeacherEditForm(instance=teacher)
    return render(request, 'school/edit_teacher.html', {'form': form, 'teacher': teacher})


@login_required
def delete_teacher(request, teacher_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    teacher = get_object_or_404(Teacher, id=teacher_id)
    if request.method == 'POST':
        user = teacher.user
        teacher.delete()
        user.delete()
        messages.success(request, 'تم حذف المعلم بنجاح')
        return redirect('teacher_list')
    return render(request, 'school/delete_teacher.html', {'teacher': teacher})


@login_required
def teacher_notes(request, teacher_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    teacher = get_object_or_404(Teacher, id=teacher_id)
    notes = TeacherNote.objects.filter(teacher=teacher).select_related('created_by').order_by('-created_at')
    return render(request, 'school/teacher_notes.html', {'teacher': teacher, 'notes': notes})


@login_required
def add_teacher_note(request, teacher_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    teacher = get_object_or_404(Teacher, id=teacher_id)
    if request.method == 'POST':
        form = TeacherNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.teacher = teacher
            note.created_by = request.user
            note.save()
            messages.success(request, 'تم إضافة الملاحظة بنجاح')
            return redirect('teacher_notes', teacher_id=teacher.id)
    else:
        form = TeacherNoteForm(initial={'teacher': teacher})
    return render(request, 'school/add_teacher_note.html', {'form': form, 'teacher': teacher})


# ─── Classes ──────────────────────────────────────────────────────────────────

@login_required
def add_class(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة الصف بنجاح')
            return redirect('class_list')
    else:
        form = ClassForm()
    return render(request, 'school/add_class.html', {'form': form})


@login_required
def class_list(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    classes = Class.objects.all().order_by('name')
    return render(request, 'school/class_list.html', {'classes': classes})


@login_required
def delete_class(request, class_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    class_obj = get_object_or_404(Class, id=class_id)
    if request.method == 'POST':
        class_obj.delete()
        messages.success(request, 'تم حذف الصف بنجاح')
        return redirect('class_list')
    return render(request, 'school/delete_class.html', {'class_obj': class_obj})


# ─── Subjects ─────────────────────────────────────────────────────────────────

@login_required
def add_subject(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة المادة بنجاح')
            return redirect('subject_list')
    else:
        form = SubjectForm()
    return render(request, 'school/add_subject.html', {'form': form})


@login_required
def subject_list(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    subjects = Subject.objects.all().order_by('name')
    return render(request, 'school/subject_list.html', {'subjects': subjects})


@login_required
def delete_subject(request, subject_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    subject = get_object_or_404(Subject, id=subject_id)
    if request.method == 'POST':
        subject.delete()
        messages.success(request, 'تم حذف المادة بنجاح')
        return redirect('subject_list')
    return render(request, 'school/delete_subject.html', {'subject': subject})


# ─── Announcements ────────────────────────────────────────────────────────────

@login_required
def announcement_list(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'school/announcement_list.html', {'announcements': announcements})


@login_required
def add_announcement(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.created_by = request.user
            announcement.save()
            messages.success(request, 'تم إضافة الإعلان بنجاح')
            return redirect('announcement_list')
    else:
        form = AnnouncementForm()
    return render(request, 'school/add_announcement.html', {'form': form})


@login_required
def delete_announcement(request, announcement_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    announcement = get_object_or_404(Announcement, id=announcement_id)
    if request.method == 'POST':
        announcement.delete()
        messages.success(request, 'تم حذف الإعلان بنجاح')
        return redirect('announcement_list')
    return render(request, 'school/delete_announcement.html', {'announcement': announcement})


# ─── Agenda ───────────────────────────────────────────────────────────────────

@login_required
def agenda_list(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    today = date.today()
    pending_items = Agenda.objects.filter(is_completed=False).order_by('due_date')
    completed_items = Agenda.objects.filter(is_completed=True).order_by('-due_date')[:20]
    return render(request, 'school/agenda_list.html', {
        'pending_items': pending_items,
        'completed_items': completed_items,
        'today': today,
    })


@login_required
def add_agenda(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = AgendaForm(request.POST)
        if form.is_valid():
            agenda = form.save(commit=False)
            agenda.created_by = request.user
            agenda.save()
            messages.success(request, 'تم إضافة مهمة جديدة للأجندة')
            return redirect('agenda_list')
    else:
        form = AgendaForm()
    return render(request, 'school/add_agenda.html', {'form': form})


@login_required
def complete_agenda(request, agenda_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    agenda = get_object_or_404(Agenda, id=agenda_id)
    agenda.is_completed = True
    agenda.save()
    messages.success(request, f'تم إكمال المهمة: {agenda.title}')
    return redirect('agenda_list')


@login_required
def uncomplete_agenda(request, agenda_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    agenda = get_object_or_404(Agenda, id=agenda_id)
    agenda.is_completed = False
    agenda.save()
    messages.success(request, f'تم إعادة فتح المهمة: {agenda.title}')
    return redirect('agenda_list')


@login_required
def delete_agenda(request, agenda_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    agenda = get_object_or_404(Agenda, id=agenda_id)
    if request.method == 'POST':
        agenda.delete()
        messages.success(request, 'تم حذف المهمة')
        return redirect('agenda_list')
    return render(request, 'school/delete_agenda.html', {'agenda': agenda})


# ─── Student Leave ────────────────────────────────────────────────────────────

@login_required
def leave_list(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    leaves = StudentLeave.objects.all().select_related('student').order_by('-created_at')
    return render(request, 'school/leave_list.html', {'leaves': leaves})


@login_required
def add_leave(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = StudentLeaveForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.approved_by = request.user
            leave.save()
            messages.success(request, 'تم تسجيل إذن المغادرة بنجاح')
            return redirect('leave_list')
    else:
        form = StudentLeaveForm()
        if request.user.profile.role == 'teacher':
            try:
                teacher = request.user.teacher_profile
                form.fields['student'].queryset = Student.objects.filter(student_class__in=teacher.classes.all())
            except Teacher.DoesNotExist:
                form.fields['student'].queryset = Student.objects.none()
    return render(request, 'school/add_leave.html', {'form': form})


@login_required
def delete_leave(request, leave_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    leave = get_object_or_404(StudentLeave, id=leave_id)
    if request.method == 'POST':
        leave.delete()
        messages.success(request, 'تم حذف إذن المغادرة')
        return redirect('leave_list')
    return render(request, 'school/delete_leave.html', {'leave': leave})


# ─── Student Levels ───────────────────────────────────────────────────────────

@login_required
def add_student_level(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = StudentLevelForm(request.POST)
        if form.is_valid():
            level = form.save(commit=False)
            level.created_by = request.user
            level.save()
            messages.success(request, 'تم إضافة مستوى الطالب بنجاح')
            return redirect('student_level_list')
    else:
        form = StudentLevelForm()
        if request.user.profile.role == 'teacher':
            try:
                teacher = request.user.teacher_profile
                form.fields['student'].queryset = Student.objects.filter(student_class__in=teacher.classes.all())
                form.fields['subject'].queryset = teacher.subjects.all()
            except Teacher.DoesNotExist:
                form.fields['student'].queryset = Student.objects.none()
                form.fields['subject'].queryset = Subject.objects.none()
    return render(request, 'school/add_student_level.html', {'form': form})


@login_required
def student_level_list(request):
    if request.user.profile.role == 'admin':
        levels = StudentLevel.objects.all().select_related('student', 'subject', 'created_by').order_by('-created_at')
    elif request.user.profile.role == 'teacher':
        try:
            teacher = request.user.teacher_profile
            levels = StudentLevel.objects.filter(
                created_by=request.user
            ).select_related('student', 'subject').order_by('-created_at')
        except Teacher.DoesNotExist:
            levels = StudentLevel.objects.none()
    else:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    return render(request, 'school/student_level_list.html', {'levels': levels})


# ─── Exam Analysis ────────────────────────────────────────────────────────────

@login_required
def add_exam_analysis(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = ExamAnalysisForm(request.POST)
        if form.is_valid():
            analysis = form.save(commit=False)
            analysis.created_by = request.user
            if analysis.total_students > 0:
                analysis.pass_percentage = round((analysis.passed_count / analysis.total_students) * 100, 2)
                analysis.fail_percentage = round((analysis.failed_count / analysis.total_students) * 100, 2)
            analysis.save()
            messages.success(request, 'تم إضافة تحليل الامتحان بنجاح')
            return redirect('exam_analysis_list')
    else:
        form = ExamAnalysisForm()
        if request.user.profile.role == 'teacher':
            try:
                teacher = request.user.teacher_profile
                form.fields['subject'].queryset = teacher.subjects.all()
                form.fields['student_class'].queryset = teacher.classes.all()
            except Teacher.DoesNotExist:
                form.fields['subject'].queryset = Subject.objects.none()
                form.fields['student_class'].queryset = Class.objects.none()
    return render(request, 'school/add_exam_analysis.html', {'form': form})


@login_required
def exam_analysis_list(request):
    if request.user.profile.role == 'admin':
        analyses = ExamAnalysis.objects.all().select_related('subject', 'student_class', 'created_by').order_by('-created_at')
    elif request.user.profile.role == 'teacher':
        try:
            teacher = request.user.teacher_profile
            analyses = ExamAnalysis.objects.filter(
                created_by=request.user
            ).select_related('subject', 'student_class').order_by('-created_at')
        except Teacher.DoesNotExist:
            analyses = ExamAnalysis.objects.none()
    else:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    return render(request, 'school/exam_analysis_list.html', {'analyses': analyses})


# ─── Messages ─────────────────────────────────────────────────────────────────

def parent_message(request):
    if request.method == 'POST':
        form = ParentMessageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إرسال رسالتك بنجاح، سيتم مراجعتها من قبل الإدارة')
            return redirect('home')
    else:
        form = ParentMessageForm()
    return render(request, 'school/parent_message.html', {'form': form})


@login_required
def message_list(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    messages_qs = Message.objects.filter(recipient__isnull=True).order_by('-created_at')
    return render(request, 'school/message_list.html', {'messages_qs': messages_qs})


@login_required
def send_message(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.save()
            messages.success(request, 'تم إرسال الرسالة بنجاح')
            return redirect('sent_messages')
    else:
        form = MessageForm()
        form.fields['recipient'].queryset = User.objects.filter(profile__role='student')
    return render(request, 'school/send_message.html', {'form': form})


@login_required
def sent_messages(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    msg_list = Message.objects.filter(sender=request.user).order_by('-created_at')
    return render(request, 'school/sent_messages.html', {'messages_qs': msg_list})


@login_required
def read_message(request, message_id):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    msg = get_object_or_404(Message, id=message_id)
    if msg.recipient and msg.recipient != request.user:
        messages.error(request, 'لا يمكنك قراءة هذه الرسالة')
        return redirect('dashboard')
    msg.is_read = True
    msg.save()
    return render(request, 'school/read_message.html', {'msg': msg})


@login_required
def student_messages(request):
    if request.user.profile.role != 'student':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    msgs = Message.objects.filter(recipient=request.user).order_by('-created_at')
    msgs.update(is_read=True)
    return render(request, 'school/student_messages.html', {'messages_qs': msgs})


# ─── Reports ──────────────────────────────────────────────────────────────────

@login_required
def reports(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    classes = Class.objects.all().order_by('name')
    return render(request, 'school/reports.html', {'classes': classes})


@login_required
def class_report(request, class_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    class_obj = get_object_or_404(Class, id=class_id)
    students = Student.objects.filter(student_class=class_obj).order_by('full_name')
    notes = Note.objects.filter(student__student_class=class_obj).order_by('-created_at')
    levels = StudentLevel.objects.filter(student__student_class=class_obj).select_related('subject').order_by('student__full_name')

    context = {
        'class_obj': class_obj,
        'students': students,
        'notes_count': notes.count(),
        'levels': levels,
    }
    return render(request, 'school/class_report.html', context)


@login_required
def reports_overview(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')

    total_students = Student.objects.count()
    total_teachers = Teacher.objects.count()
    total_classes = Class.objects.count()
    total_notes = Note.objects.count()
    total_leaves = StudentLeave.objects.count()
    total_exams = ExamAnalysis.objects.count()

    class_stats = []
    for cls in Class.objects.all().order_by('name'):
        student_count = Student.objects.filter(student_class=cls).count()
        notes_count = Note.objects.filter(student__student_class=cls).count()
        class_stats.append({
            'name': cls.name,
            'students': student_count,
            'notes': notes_count,
        })

    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_classes': total_classes,
        'total_notes': total_notes,
        'total_leaves': total_leaves,
        'total_exams': total_exams,
        'class_stats': class_stats,
    }
    return render(request, 'school/reports_overview.html', context)


# ─── WhatsApp ─────────────────────────────────────────────────────────────────

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
