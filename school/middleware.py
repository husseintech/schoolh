import re

from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect


class StudentRecordAccessMiddleware:
    """Protect direct student record URLs and sensitive destructive endpoints.

    - Student reports contain sensitive administrative history, so they are
      restricted to the admin role.
    - Student detail pages may be viewed by administrative roles, by a teacher
      only for students in the teacher's assigned classes, or by the student
      for their own record.
    - Destructive message/visit endpoints that already use POST forms in the UI
      are refused on GET so a simple link cannot trigger a deletion.
    """

    _student_record_re = re.compile(r'^/students/(\d+)/(detail|report)/$')
    _message_delete_re = re.compile(r'^/messages/(?:\d+/delete/|delete-all(?:-sent|-received)?/)$')
    _visit_program_delete_re = re.compile(r'^/visit-program/\d+/delete/$')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # The current templates submit these operations as POST with CSRF tokens.
        # Refuse GET/HEAD access so deletions cannot be triggered by opening a URL.
        if self._message_delete_re.match(request.path) or self._visit_program_delete_re.match(request.path):
            if request.method != 'POST':
                return HttpResponseNotAllowed(['POST'])

        match = self._student_record_re.match(request.path)
        if match and getattr(request, 'user', None) and request.user.is_authenticated:
            student_id = int(match.group(1))
            page_type = match.group(2)
            role = getattr(getattr(request.user, 'profile', None), 'role', None)

            # Full student reports can include administrative/private history.
            if page_type == 'report':
                if role != 'admin':
                    messages.error(request, 'ليس لديك صلاحية للوصول إلى تقرير هذا الطالب')
                    return redirect('dashboard')

            elif page_type == 'detail':
                allowed = False

                if role in ('admin', 'vice_principal', 'secretary'):
                    allowed = True
                elif role == 'student':
                    student_profile = getattr(request.user, 'student_profile', None)
                    allowed = bool(student_profile and student_profile.id == student_id)
                elif role == 'teacher':
                    teacher = getattr(request.user, 'teacher_profile', None)
                    if teacher:
                        from .models import Student
                        allowed = Student.objects.filter(
                            id=student_id,
                            student_class__in=teacher.classes.all(),
                        ).exists()

                if not allowed:
                    messages.error(request, 'ليس لديك صلاحية للوصول إلى بيانات هذا الطالب')
                    return redirect('dashboard')

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
