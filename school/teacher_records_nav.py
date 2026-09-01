import re

from .reset_data_teacher_records import handle_teacher_record_reset, reset_rows_html


class TeacherRecordsNavigationMiddleware:
    """Expose teacher registers in the legacy UI and integrate their reset rows safely."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and request.path.rstrip('/') == '/reset-data':
            handled = handle_teacher_record_reset(request)
            if handled is not None:
                return handled

        response = self.get_response(request)
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or 'text/html' not in response.get('Content-Type', ''):
            return response
        try:
            role = user.profile.role
            html = response.content.decode(response.charset or 'utf-8')
        except Exception:
            return response

        marker = '<div class="nav-collapse" id="collapse-admin">'
        if marker in html and 'data-school-records-nav="1"' not in html:
            links = []
            if role == 'admin':
                links.append('<a data-school-records-nav="1" href="/administration/teacher-records/class-subjects/" class="nav-link"><i class="bi bi-diagram-3"></i> مواد الصفوف</a>')
            if role in ('admin', 'vice_principal', 'teacher'):
                links.append('<a data-school-records-nav="1" href="/administration/academic-achievement/" class="nav-link"><i class="bi bi-clipboard-data"></i> تحليل التحصيل الدراسي</a>')
                links.append('<a data-school-records-nav="1" href="/administration/teacher-records/curriculum/" class="nav-link"><i class="bi bi-journal-check"></i> متابعة ما قطع من المنهاج</a>')
                links.append('<a data-school-records-nav="1" href="/administration/teacher-records/training/" class="nav-link"><i class="bi bi-mortarboard"></i> سجل الدورات</a>')
            if links:
                html = html.replace(marker, marker + ''.join(links), 1)

        if role == 'admin' and request.path.rstrip('/') == '/reset-data' and 'data-teacher-record-reset="1"' not in html:
            token_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
            if token_match:
                rows = reset_rows_html(token_match.group(1))
                tbody_end = '</tbody>'
                if tbody_end in html:
                    html = html.replace(tbody_end, rows + tbody_end, 1)

        response.content = html.encode(response.charset or 'utf-8')
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
        return response
