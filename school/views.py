import os, io, csv
from datetime import date, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Q
from django.conf import settings
from dotenv import set_key
from .models import Profile, Student, Note, Teacher, TeacherNote, Announcement, Agenda, StudentLeave, StudentLevel, ExamAnalysis, Message, Class, Subject, UserPermission, DEFAULT_PERMISSIONS, has_perm, can_view, LessonLink, StudentLateness, SchoolInfo, Meeting
from .forms import (StudentForm, NoteForm, StudentEditForm, TeacherForm, TeacherEditForm,
    TeacherNoteForm, AnnouncementForm, AgendaForm, AgendaCompleteForm,
    StudentLeaveForm, StudentLevelForm, ExamAnalysisForm, MessageForm,
    ParentMessageForm, ClassForm, SubjectForm)
from .services import send_whatsapp_message


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('home')
        messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة')
        return redirect('home')
    return redirect('home')


def logout_view(request):
    logout(request)
    return redirect('home')


def home(request):
    from datetime import datetime, timedelta
    announcements = Announcement.objects.filter(is_active=True)[:5]
    lesson_links = LessonLink.objects.filter(is_active=True)[:10]
    now = datetime.now()
    now_ago = now - timedelta(hours=1)
    return render(request, 'school/home.html', {
        'announcements': announcements,
        'lesson_links': lesson_links,
        'now': now,
        'now_ago': now_ago,
    })


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
    if not has_perm(request.user, 'students', 'add'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            username = form.cleaned_data['username']
            password = form.cleaned_data.get('password')
            if not password:
                password = form.cleaned_data['student_id'][-6:] if len(form.cleaned_data['student_id']) >= 6 else form.cleaned_data['student_id']
            messages.success(request, f'تم إضافة الطالب بنجاح\nاسم المستخدم: {username}\nكلمة المرور: {password}')
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


@login_required
def reset_student_password(request, student_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        if len(new_password) < 4:
            messages.error(request, 'كلمة المرور يجب أن تكون 4 أحرف على الأقل')
            return redirect('reset_student_password', student_id=student.id)
        student.user.set_password(new_password)
        student.user.save()
        student.plain_password = new_password
        student.save()
        messages.success(request, f'تم تغيير كلمة مرور الطالب {student.full_name} إلى: {new_password}')
        return redirect('student_detail', student_id=student.id)
    return render(request, 'school/reset_password.html', {'student': student})


@login_required
def student_report(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    leaves = StudentLeave.objects.filter(student=student).order_by('-created_at')
    notes = Note.objects.filter(student=student).select_related('created_by').order_by('-created_at')
    principal_name = ''
    principal_phone = ''
    if request.user.profile.role == 'admin':
        principal_name = request.user.first_name or request.user.username
        principal_phone = request.user.profile.phone
    return render(request, 'school/student_report.html', {
        'student': student,
        'leaves': leaves,
        'notes': notes,
        'principal_name': principal_name,
        'principal_phone': principal_phone,
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

    headers = ['الاسم الكامل', 'رقم الهوية', 'الصف', 'هاتف ولي الأمر', 'اسم ولي الأمر', 'العنوان', 'تاريخ الميلاد', 'كلمة المرور']
    ws.append(headers)

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill(start_color="2c3e50", end_color="2c3e50", fill_type="solid")
        cell.alignment = openpyxl.styles.Alignment(horizontal='center')

    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 20
    ws.column_dimensions['F'].width = 30
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 18

    ws.merge_cells('I1:J1')
    note_cell = ws.cell(row=1, column=9, value='كلمة المرور اختيارية - اذا تركت فارغة سيتم إنشاءها تلقائياً من آخر 6 أرقام من رقم الهوية')
    note_cell.font = openpyxl.styles.Font(size=9, color="e74c3c")

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
                password = str(row[7]).strip() if len(row) > 7 and row[7] else ''

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
                if not password:
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
                    plain_password=password,
                )
                imported += 1
            except Exception as e:
                errors.append(f'الصف {i}: خطأ - {str(e)}')

        if imported:
            msg = f'تم استيراد {imported} طالب/طالب بنجاح'
            if imported <= 5:
                messages.success(request, f'{msg}\nاسم المستخدم لكل طالب: student_[رقم الهوية]\nكلمة المرور: آخر 6 أرقام من رقم الهوية')
            else:
                messages.success(request, f'{msg}\nاسم المستخدم: student_[رقم الهوية]\nكلمة المرور الافتراضية: آخر 6 أرقام من رقم الهوية')
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
def add_note(request, student_id=None):
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
        initial = {}
        if student_id:
            initial['student'] = get_object_or_404(Student, id=student_id)
        form = NoteForm(initial=initial)
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
    if not has_perm(request.user, 'teachers', 'add'):
        messages.error(request, 'ليس لديك صلاحية')
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
    if not has_perm(request.user, 'teachers', 'view'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    teachers = Teacher.objects.all().prefetch_related('classes', 'subjects').order_by('full_name')
    return render(request, 'school/teacher_list.html', {'teachers': teachers})


@login_required
def edit_teacher(request, teacher_id):
    if not has_perm(request.user, 'teachers', 'edit'):
        messages.error(request, 'ليس لديك صلاحية')
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
    if not has_perm(request.user, 'teachers', 'delete'):
        messages.error(request, 'ليس لديك صلاحية')
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
def teachers_report(request):
    if not has_perm(request.user, 'teachers', 'view'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    teachers = Teacher.objects.all().prefetch_related('classes', 'subjects').order_by('full_name')
    return render(request, 'school/teachers_report.html', {'teachers': teachers})


@login_required
def notes_report(request):
    if not has_perm(request.user, 'notes', 'view'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    notes = Note.objects.all().select_related('student__student_class', 'created_by').order_by('-created_at')
    return render(request, 'school/notes_report.html', {'notes': notes})


@login_required
def school_info_view(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    info = SchoolInfo.objects.first()
    if request.method == 'POST':
        name_ar = request.POST.get('name_ar', '')
        name_en = request.POST.get('name_en', '')
        principal_name = request.POST.get('principal_name', '')
        national_number = request.POST.get('national_number', '')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        if info:
            info.name_ar = name_ar
            info.name_en = name_en
            info.principal_name = principal_name
            info.national_number = national_number
            info.latitude = float(latitude) if latitude else None
            info.longitude = float(longitude) if longitude else None
            info.save()
        else:
            SchoolInfo.objects.create(name_ar=name_ar, name_en=name_en,
                principal_name=principal_name, national_number=national_number,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None)
        messages.success(request, 'تم حفظ بيانات المدرسة')
        return redirect('dashboard')
    return render(request, 'school/school_info.html', {'info': info})


@login_required
def add_meeting(request):
    if not has_perm(request.user, 'meetings', 'add'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    teachers = Teacher.objects.all().order_by('full_name')
    if request.method == 'POST':
        meeting_type = request.POST.get('meeting_type')
        date_val = request.POST.get('date')
        day = request.POST.get('day')
        time_val = request.POST.get('time')
        place = request.POST.get('place')
        goals = request.POST.get('goals', '')
        minutes = request.POST.get('minutes', '')
        meeting_number = request.POST.get('meeting_number')
        all_teachers = request.POST.get('all_teachers') == 'on'
        attendee_ids = request.POST.getlist('attendees')
        meeting = Meeting.objects.create(
            meeting_type=meeting_type, date=date_val, day=day, time=time_val,
            place=place, goals=goals, minutes=minutes,
            meeting_number=meeting_number, all_teachers=all_teachers,
            created_by=request.user
        )
        if all_teachers:
            meeting.attendees.set(Teacher.objects.all())
        elif attendee_ids:
            meeting.attendees.set(attendee_ids)
        messages.success(request, f'تم تسجيل الاجتماع رقم {meeting_number}')
        return redirect('meeting_list')
    return render(request, 'school/add_meeting.html', {'teachers': teachers})


@login_required
def meeting_list(request):
    if not has_perm(request.user, 'meetings', 'view'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    meetings = Meeting.objects.all().order_by('-date')
    return render(request, 'school/meeting_list.html', {'meetings': meetings})


@login_required
def meeting_report(request, meeting_id):
    if not has_perm(request.user, 'meetings', 'view'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    meeting = get_object_or_404(Meeting.objects.prefetch_related('attendees'), id=meeting_id)
    info = SchoolInfo.objects.first()
    return render(request, 'school/meeting_report.html', {'meeting': meeting, 'info': info})


@login_required
def add_teacher_note(request, teacher_id):
    if not has_perm(request.user, 'teachers', 'notes'):
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
    leaves = StudentLeave.objects.all().select_related('student__student_class').order_by('-created_at')
    student_id = request.GET.get('student_id', '')
    search_query = request.GET.get('q', '')
    if student_id:
        leaves = leaves.filter(student_id=student_id)
    elif search_query:
        leaves = leaves.filter(student__full_name__icontains=search_query)
    students = Student.objects.all().order_by('full_name')
    return render(request, 'school/leave_list.html', {
        'leaves': leaves,
        'students': students,
        'selected_student': student_id,
        'search_query': search_query,
    })


@login_required
def add_leave(request, student_id=None):
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
        initial = {}
        if student_id:
            initial['student'] = get_object_or_404(Student, id=student_id)
        form = StudentLeaveForm(initial=initial)
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
def bulk_add_student_level(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    try:
        teacher = request.user.teacher_profile
    except Teacher.DoesNotExist:
        if request.user.profile.role != 'admin':
            messages.error(request, 'يجب أن تكون معلماً لتسجيل المستويات')
            return redirect('dashboard')
        teacher = None
    if teacher:
        classes = teacher.classes.all().order_by('name')
        subjects_qs = teacher.subjects.all()
    else:
        classes = Class.objects.all().order_by('name')
        subjects_qs = Subject.objects.all()
    if request.method == 'POST':
        students_ids = request.POST.getlist('student_id')
        levels = request.POST.getlist('level')
        notes_list = request.POST.getlist('notes')
        subject_id = request.POST.get('subject')
        class_id = request.POST.get('class_id')
        subject = Subject.objects.get(id=subject_id) if subject_id else None
        count = 0
        for i, student_id in enumerate(students_ids):
            if levels[i]:
                StudentLevel.objects.create(
                    student_id=student_id,
                    subject=subject,
                    level=levels[i],
                    notes=notes_list[i] if i < len(notes_list) else '',
                    created_by=request.user
                )
                count += 1
        messages.success(request, f'تم تسجيل {count} مستوى بنجاح')
        return redirect('student_level_list')
    class_id = request.GET.get('class_id')
    selected_class = None
    students = []
    if class_id:
        selected_class = get_object_or_404(Class, id=class_id)
        if teacher and selected_class not in teacher.classes.all():
            messages.error(request, 'ليس لديك صلاحية للوصول إلى هذا الصف')
            return redirect('bulk_add_student_level')
        students = Student.objects.filter(student_class=selected_class).order_by('full_name')
    return render(request, 'school/bulk_add_student_level.html', {
        'students': students,
        'subjects': subjects_qs,
        'classes': classes,
        'selected_class': selected_class,
    })

def add_student_level(request):
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    try:
        teacher = request.user.teacher_profile
    except Teacher.DoesNotExist:
        if request.user.profile.role != 'admin':
            messages.error(request, 'يجب أن تكون معلماً لتسجيل المستويات')
            return redirect('dashboard')
        teacher = None
    if teacher:
        classes = teacher.classes.all().order_by('name')
        subjects_qs = teacher.subjects.all()
    else:
        classes = Class.objects.all().order_by('name')
        subjects_qs = Subject.objects.all()
    if request.method == 'POST':
        students_ids = request.POST.getlist('student_id')
        levels = request.POST.getlist('level')
        notes_list = request.POST.getlist('notes')
        subject_id = request.POST.get('subject')
        class_id = request.POST.get('class_id')
        subject = Subject.objects.get(id=subject_id) if subject_id else None
        count = 0
        for i, student_id in enumerate(students_ids):
            if levels[i]:
                StudentLevel.objects.create(
                    student_id=student_id,
                    subject=subject,
                    level=levels[i],
                    notes=notes_list[i] if i < len(notes_list) else '',
                    created_by=request.user
                )
                count += 1
        messages.success(request, f'تم تسجيل {count} مستوى بنجاح')
        return redirect('student_level_list')
    class_id = request.GET.get('class_id')
    selected_class = None
    students = []
    if class_id:
        selected_class = get_object_or_404(Class, id=class_id)
        if teacher and selected_class not in teacher.classes.all():
            messages.error(request, 'ليس لديك صلاحية للوصول إلى هذا الصف')
            return redirect('add_student_level')
        students = Student.objects.filter(student_class=selected_class).order_by('full_name')
    return render(request, 'school/add_student_level.html', {
        'students': students,
        'subjects': subjects_qs,
        'classes': classes,
        'selected_class': selected_class,
    })


@login_required
def student_level_list(request):
    if request.user.profile.role == 'admin':
        levels_qs = StudentLevel.objects.all().select_related('student', 'subject', 'created_by').order_by('-created_at')
    elif request.user.profile.role == 'teacher':
        try:
            teacher = request.user.teacher_profile
            levels_qs = StudentLevel.objects.filter(
                created_by=request.user
            ).select_related('student', 'subject').order_by('-created_at')
        except Teacher.DoesNotExist:
            levels_qs = StudentLevel.objects.none()
    else:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    classes = Class.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    selected_class = None
    selected_subject = None
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    if class_id and subject_id:
        selected_class = get_object_or_404(Class, id=class_id)
        selected_subject = get_object_or_404(Subject, id=subject_id)
        levels_qs = levels_qs.filter(student__student_class=selected_class, subject=selected_subject)
    elif class_id:
        selected_class = get_object_or_404(Class, id=class_id)
        levels_qs = levels_qs.filter(student__student_class=selected_class)
    return render(request, 'school/student_level_list.html', {
        'levels': levels_qs,
        'classes': classes,
        'subjects': subjects,
        'selected_class': selected_class,
        'selected_subject': selected_subject,
    })


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
def student_levels_report(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    classes = Class.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    selected_class = None
    selected_subject = None
    levels = []
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    if class_id and subject_id:
        selected_class = get_object_or_404(Class, id=class_id)
        selected_subject = get_object_or_404(Subject, id=subject_id)
        levels = StudentLevel.objects.filter(
            student__student_class=selected_class,
            subject=selected_subject
        ).select_related('student', 'created_by').order_by('student__full_name')
    return render(request, 'school/student_levels_report.html', {
        'classes': classes,
        'subjects': subjects,
        'selected_class': selected_class,
        'selected_subject': selected_subject,
        'levels': levels,
    })


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
            'id': cls.id,
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


# ─── Account Management ───────────────────────────────────────────────────────

@login_required
def account_list(request):
    if not has_perm(request.user, 'settings', 'accounts'):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    admins = User.objects.filter(is_superuser=False, profile__role='admin').select_related('profile')
    vice_principals = User.objects.filter(is_superuser=False, profile__role='vice_principal').select_related('profile')
    secretaries = User.objects.filter(is_superuser=False, profile__role='secretary').select_related('profile')
    teachers = User.objects.filter(is_superuser=False, profile__role='teacher').select_related('profile')
    students = User.objects.filter(is_superuser=False, profile__role='student').select_related('profile')
    return render(request, 'school/account_list.html', {
        'admins': admins,
        'vice_principals': vice_principals,
        'secretaries': secretaries,
        'teachers': teachers,
        'students': students,
    })


@login_required
def add_account(request):
    if not has_perm(request.user, 'settings', 'accounts'):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        role = request.POST.get('role', '')
        phone = request.POST.get('phone', '').strip()

        if not username or not password:
            messages.error(request, 'اسم المستخدم وكلمة المرور مطلوبان')
            return redirect('add_account')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'اسم المستخدم موجود مسبقاً')
            return redirect('add_account')

        user = User.objects.create_user(username=username, password=password, first_name=full_name)
        Profile.objects.create(user=user, role=role, phone=phone)

        new_perms = {}
        for key, val in request.POST.items():
            if key.startswith('perm_'):
                parts = key.replace('perm_', '', 1).rsplit('_', 1)
                if len(parts) == 2:
                    module, action = parts
                    new_perms.setdefault(module, []).append(action)
        if not new_perms:
            new_perms = UserPermission.get_defaults(role)
        UserPermission.objects.create(user=user, permissions=new_perms)

        messages.success(request, f'تم إضافة الحساب: {username} - {dict(Profile.ROLE_CHOICES).get(role, "")}')
        return redirect('account_list')

    MODULE_KEYS = ['students', 'teachers', 'classes', 'subjects', 'announcements', 'agenda', 'leaves', 'levels', 'exams', 'messages', 'reports', 'settings', 'notes', 'lateness']
    ACTION_KEYS = ['view', 'add', 'edit', 'delete', 'import', 'export', 'notes', 'complete', 'send', 'whatsapp', 'accounts']
    MODULE_LABELS = {
        'students': 'الطلاب',
        'teachers': 'المعلمون',
        'classes': 'الصفوف',
        'subjects': 'المواد',
        'announcements': 'الإعلانات',
        'agenda': 'الأجندة',
        'leaves': 'أذونات المغادرة',
        'levels': 'مستويات الطلاب',
        'exams': 'تحليل الامتحانات',
        'messages': 'الرسائل',
        'reports': 'التقارير',
        'settings': 'الإعدادات',
'notes': 'الملاحظات',
        'lateness': 'تأخيرات الطلاب',
    }
    ACTION_LABELS = {
        'view': 'عرض',
        'add': 'إضافة',
        'edit': 'تعديل',
        'delete': 'حذف',
        'import': 'استيراد',
        'export': 'تصدير',
        'notes': 'ملاحظات',
        'complete': 'إكمال',
        'send': 'إرسال',
        'whatsapp': 'واتساب',
        'accounts': 'الحسابات',
    }
    modules = [{'key': k, 'label': MODULE_LABELS[k]} for k in MODULE_KEYS]
    actions = [{'key': k, 'label': ACTION_LABELS[k]} for k in ACTION_KEYS]
    return render(request, 'school/add_account.html', {
        'roles': Profile.ROLE_CHOICES,
        'modules': modules,
        'actions': actions,
        'default_perms': DEFAULT_PERMISSIONS,
    })


@login_required
def edit_account(request, user_id):
    if not has_perm(request.user, 'settings', 'accounts'):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    perms, _ = UserPermission.objects.get_or_create(user=user, defaults={'permissions': UserPermission.get_defaults(profile.role)})

    if request.method == 'POST':
        profile.role = request.POST.get('role', profile.role)
        profile.phone = request.POST.get('phone', '')
        user.first_name = request.POST.get('full_name', '')
        profile.save()
        user.save()

        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            user.set_password(new_password)
            user.save()

        new_perms = {}
        for key, val in request.POST.items():
            if key.startswith('perm_'):
                parts = key.replace('perm_', '', 1).rsplit('_', 1)
                if len(parts) == 2:
                    module, action = parts
                    new_perms.setdefault(module, []).append(action)
        perms.permissions = new_perms
        perms.save()

        messages.success(request, f'تم تحديث الحساب: {user.username}')
        return redirect('account_list')

    MODULE_KEYS = ['students', 'teachers', 'classes', 'subjects', 'announcements', 'agenda', 'leaves', 'levels', 'exams', 'messages', 'reports', 'settings', 'notes', 'lateness']
    ACTION_KEYS = ['view', 'add', 'edit', 'delete', 'import', 'export', 'notes', 'complete', 'send', 'whatsapp', 'accounts']
    MODULE_LABELS = {
        'students': 'الطلاب',
        'teachers': 'المعلمون',
        'classes': 'الصفوف',
        'subjects': 'المواد',
        'announcements': 'الإعلانات',
        'agenda': 'الأجندة',
        'leaves': 'أذونات المغادرة',
        'levels': 'مستويات الطلاب',
        'exams': 'تحليل الامتحانات',
        'messages': 'الرسائل',
        'reports': 'التقارير',
        'settings': 'الإعدادات',
'notes': 'الملاحظات',
        'lateness': 'تأخيرات الطلاب',
    }
    ACTION_LABELS = {
        'view': 'عرض',
        'add': 'إضافة',
        'edit': 'تعديل',
        'delete': 'حذف',
        'import': 'استيراد',
        'export': 'تصدير',
        'notes': 'ملاحظات',
        'complete': 'إكمال',
        'send': 'إرسال',
        'whatsapp': 'واتساب',
        'accounts': 'الحسابات',
    }
    modules = [{'key': k, 'label': MODULE_LABELS[k]} for k in MODULE_KEYS]
    actions = [{'key': k, 'label': ACTION_LABELS[k]} for k in ACTION_KEYS]

    allowed_set = set()
    for module, actions_list in perms.permissions.items():
        for action in actions_list:
            allowed_set.add(f'{module}_{action}')

    return render(request, 'school/edit_account.html', {
        'edit_user': user,
        'profile': profile,
        'allowed_set': allowed_set,
        'roles': Profile.ROLE_CHOICES,
        'modules': modules,
        'actions': actions,
        'default_perms': DEFAULT_PERMISSIONS,
    })


@login_required
def delete_account(request, user_id):
    if not has_perm(request.user, 'settings', 'accounts'):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, 'لا يمكنك حذف حسابك الخاص')
        return redirect('account_list')
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'تم حذف الحساب: {username}')
        return redirect('account_list')
    return render(request, 'school/delete_account.html', {'del_user': user})


@login_required
def my_account(request):
    user = request.user
    profile = user.profile
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        if full_name:
            user.first_name = full_name
        if phone:
            profile.phone = phone
        if new_password:
            user.set_password(new_password)
        profile.save()
        user.save()
        if new_password:
            messages.success(request, 'تم تغيير كلمة المرور. سجل دخول مرة أخرى')
            return redirect('login')
        messages.success(request, 'تم تحديث البيانات')
        return redirect('my_account')
    return render(request, 'school/my_account.html', {'profile': profile})


# ─── Lesson Links (Online Classes) ──────────────────────────────────────────

@login_required
def lesson_link_list(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    links = LessonLink.objects.all().order_by('-lesson_datetime', '-created_at')
    return render(request, 'school/lesson_link_list.html', {'links': links})


@login_required
def add_lesson_link(request):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        url = request.POST.get('url', '').strip()
        lesson_date = request.POST.get('lesson_date', '').strip()
        lesson_time = request.POST.get('lesson_time', '').strip()
        if not title or not url:
            messages.error(request, 'العنوان والرابط مطلوبان')
            return redirect('add_lesson_link')
        dt = None
        if lesson_date and lesson_time:
            from datetime import datetime as dt_mod
            try:
                dt = dt_mod.strptime(f'{lesson_date} {lesson_time}', '%Y-%m-%d %H:%M')
            except ValueError:
                pass
        LessonLink.objects.create(title=title, url=url, lesson_datetime=dt)
        messages.success(request, f'تم إضافة الرابط: {title}')
        return redirect('lesson_link_list')
    return render(request, 'school/add_lesson_link.html')


@login_required
def delete_lesson_link(request, link_id):
    if request.user.profile.role != 'admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    link = get_object_or_404(LessonLink, id=link_id)
    if request.method == 'POST':
        title = link.title
        link.delete()
        messages.success(request, f'تم حذف الرابط: {title}')
        return redirect('lesson_link_list')
    return render(request, 'school/delete_lesson_link.html', {'link': link})


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


# ─── Student Lateness ─────────────────────────────────────────────────────────

@login_required
def lateness_list(request):
    if not has_perm(request.user, 'lateness', 'view'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    classes = Class.objects.all().order_by('name')
    students = Student.objects.all().select_related('student_class').order_by('student_class__name', 'full_name')
    search_query = request.GET.get('q', '')
    if search_query:
        students = students.filter(full_name__icontains=search_query)
    students = students.annotate(lateness_count=Count('lateness'))
    today_lateness = list(StudentLateness.objects.filter(date=date.today()).values_list('student_id', flat=True))
    today_notes = {
        l.student_id: l.notes
        for l in StudentLateness.objects.filter(date=date.today())
    }
    for s in students:
        s.lateness_notes = today_notes.get(s.id, '')
    if request.method == 'POST':
        if not has_perm(request.user, 'lateness', 'add'):
            messages.error(request, 'ليس لديك صلاحية للإضافة')
            return redirect('lateness_list')
        student_ids = request.POST.getlist('student_id')
        lateness_date = request.POST.get('lateness_date', str(date.today()))
        count = 0
        for sid in student_ids:
            note = request.POST.get(f'notes_{sid}', '')
            StudentLateness.objects.update_or_create(
                student_id=sid,
                date=lateness_date,
                defaults={'notes': note, 'created_by': request.user}
            )
            count += 1
        messages.success(request, f'تم تسجيل تأخير {count} طالب/طلاب')
        return redirect('lateness_list')
    return render(request, 'school/lateness_list.html', {
        'students': students,
        'classes': classes,
        'search_query': search_query,
        'today_lateness': today_lateness,
        'today': date.today(),
    })


@login_required
def lateness_report(request):
    if not has_perm(request.user, 'lateness', 'view'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    month = request.GET.get('month', '')
    year = request.GET.get('year', '')
    lateness_qs = StudentLateness.objects.all().select_related('student', 'created_by')
    if month:
        lateness_qs = lateness_qs.filter(date__month=month)
    if year:
        lateness_qs = lateness_qs.filter(date__year=year)
    else:
        lateness_qs = lateness_qs.filter(date__year=date.today().year)
    lateness_qs = lateness_qs.order_by('-date', 'student__full_name')
    months = [
        ('1', 'يناير'), ('2', 'فبراير'), ('3', 'مارس'), ('4', 'إبريل'),
        ('5', 'مايو'), ('6', 'يونيو'), ('7', 'يوليو'), ('8', 'أغسطس'),
        ('9', 'سبتمبر'), ('10', 'أكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
    ]
    return render(request, 'school/lateness_report.html', {
        'lateness_list': lateness_qs,
        'months': months,
        'selected_month': month,
        'selected_year': year or str(date.today().year),
    })


@login_required
def student_lateness_detail(request, student_id):
    if not has_perm(request.user, 'lateness', 'view'):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    student = get_object_or_404(Student, id=student_id)
    lateness_records = StudentLateness.objects.filter(student=student).select_related('created_by').order_by('-date')
    return render(request, 'school/student_lateness_detail.html', {
        'student': student,
        'lateness_records': lateness_records,
    })

