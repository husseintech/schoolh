import re

from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render


class StudentRecordAccessMiddleware:
    """Protect direct student-record URLs and selected state-changing endpoints."""

    _student_record_re = re.compile(r'^/students/(\d+)/(detail|report)/$')
    _student_lateness_re = re.compile(r'^/lateness/student/(\d+)/$')
    _student_survey_re = re.compile(r'^/survey/(\d+)/$')

    _message_delete_re = re.compile(r'^/messages/(?:\d+/delete/|delete-all(?:-sent|-received)?/)$')
    _visit_program_delete_re = re.compile(r'^/visit-program/\d+/delete/$')
    _whatsapp_group_delete_re = re.compile(r'^/whatsapp-groups/\d+/delete/$')
    _secretary_delete_re = re.compile(r'^/secretary/(?:incoming|outgoing)/\d+/delete/$')
    _followup_delete_re = re.compile(r'^/followups/\d+/delete/$')
    _no_objection_delete_re = re.compile(r'^/secretary/no-objection/\d+/delete/$')
    _reciprocal_visit_delete_re = re.compile(r'^/reciprocal-visits/\d+/delete/$')
    _agenda_mutation_re = re.compile(r'^/agenda/\d+/(?:complete|uncomplete|delete)/$')

    _open_learning_confirm_re = re.compile(
        r'^/open-learning/lessons/\d+/(?:submit|approve|publish|archive)/$'
    )
    _open_learning_resource_delete_re = re.compile(
        r'^/open-learning/lessons/\d+/resources/\d+/delete/$'
    )

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _can_access_student(user, student_id):
        role = getattr(getattr(user, 'profile', None), 'role', None)
        if role == 'admin':
            return True
        if role == 'student':
            student_profile = getattr(user, 'student_profile', None)
            return bool(student_profile and student_profile.id == student_id)

        from .models import Student, has_perm
        if role in ('vice_principal', 'secretary'):
            return has_perm(user, 'students', 'view')
        if role == 'teacher':
            if not has_perm(user, 'students', 'view'):
                return False
            teacher = getattr(user, 'teacher_profile', None)
            if teacher:
                return Student.objects.filter(
                    id=student_id,
                    student_class__in=teacher.classes.all(),
                ).exists()
        return False

    def __call__(self, request):
        protected_mutation = (
            self._message_delete_re.match(request.path)
            or self._visit_program_delete_re.match(request.path)
            or self._whatsapp_group_delete_re.match(request.path)
            or self._secretary_delete_re.match(request.path)
            or self._followup_delete_re.match(request.path)
            or self._no_objection_delete_re.match(request.path)
            or self._reciprocal_visit_delete_re.match(request.path)
            or self._agenda_mutation_re.match(request.path)
        )
        if protected_mutation and request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])

        open_learning_mutation = (
            self._open_learning_confirm_re.match(request.path)
            or self._open_learning_resource_delete_re.match(request.path)
        )
        if open_learning_mutation:
            if request.method == 'GET':
                return render(request, 'school/security_confirm.html')
            if request.method != 'POST':
                return HttpResponseNotAllowed(['GET', 'POST'])

        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            role = getattr(getattr(user, 'profile', None), 'role', None)

            # Guardian accounts are deliberately read-only and scoped to the
            # dedicated guardian portal. This prevents a guardian account from
            # falling through generic "non-student" branches in legacy views.
            if role == 'guardian' and request.path.startswith('/open-learning/'):
                if not request.path.startswith('/open-learning/guardian/'):
                    return redirect('ol_guardian_portal')

            match = self._student_record_re.match(request.path)
            if match:
                student_id = int(match.group(1))
                page_type = match.group(2)
                if page_type == 'report':
                    if role != 'admin':
                        messages.error(request, 'ليس لديك صلاحية للوصول إلى تقرير هذا الطالب')
                        return redirect('dashboard')
                elif not self._can_access_student(user, student_id):
                    messages.error(request, 'ليس لديك صلاحية للوصول إلى بيانات هذا الطالب')
                    return redirect('dashboard')

            sensitive_matches = (
                self._student_lateness_re.match(request.path),
                self._student_survey_re.match(request.path),
            )
            for sensitive_match in sensitive_matches:
                if sensitive_match:
                    student_id = int(sensitive_match.group(1))
                    if not self._can_access_student(user, student_id):
                        messages.error(request, 'ليس لديك صلاحية للوصول إلى بيانات هذا الطالب')
                        return redirect('dashboard')
                    break

        return self.get_response(request)


class WordExportMiddleware:
    """يحول أي صفحة HTML تُطلب بـ ?export=word إلى ملف Word (.doc) قابل للتحميل."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.GET.get('export') != 'word':
            return response
        if not response.get('Content-Type', '').startswith('text/html'):
            return response
        slug = re.sub(r'[^a-zA-Z0-9_-]+', '_', request.path.strip('/')).strip('_') or 'report'
        response['Content-Type'] = 'application/msword'
        response['Content-Disposition'] = f'attachment; filename="{slug}.doc"'
        if hasattr(response, 'content') and isinstance(response.content, bytes):
            try:
                html = response.content.decode('utf-8')
                head_end = html.find('</head>')
                if head_end != -1:
                    inject = (
                        '<meta name="ProgId" content="Word.Document">'
                        '<!--[if gte mso 9]><xml>'
                        '<w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom></w:WordDocument>'
                        '</xml><![endif]-->'
                    )
                    html = html[:head_end] + inject + html[head_end:]
                    response.content = html.encode('utf-8')
            except (UnicodeDecodeError, AttributeError):
                pass
        return response
