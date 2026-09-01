class TeacherRecordsNavigationMiddleware:
    """Expose the new school registers in the legacy administration UI safely."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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

        if role == 'admin' and request.path.rstrip('/') == '/reset-data' and 'teacher-records-reset-link' not in html:
            anchor = '<a href="/administration/teacher-records/reset/" id="teacher-records-reset-link" class="btn btn-outline-danger"><i class="bi bi-eraser"></i> تفريغ سجلات المعلمين ومواد الصفوف</a> '
            target = '<a href="/backup/"'
            if target in html:
                html = html.replace(target, anchor + target, 1)

        response.content = html.encode(response.charset or 'utf-8')
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
        return response
