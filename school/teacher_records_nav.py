class TeacherRecordsNavigationMiddleware:
    """Add the new school registers to the existing administration sidebar without changing legacy menu markup."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, 'user', None)
        ctype = response.get('Content-Type', '')
        if not user or not user.is_authenticated or 'text/html' not in ctype:
            return response
        try:
            role = user.profile.role
        except Exception:
            return response
        marker = '<div class="nav-collapse" id="collapse-admin">'
        try:
            html = response.content.decode(response.charset or 'utf-8')
        except Exception:
            return response
        if marker not in html or 'data-school-records-nav="1"' in html:
            return response
        links = []
        if role in ('admin', 'vice_principal'):
            links.append('<a data-school-records-nav="1" href="/administration/academic-achievement/" class="nav-link"><i class="bi bi-clipboard-data"></i> تحليل التحصيل الدراسي</a>')
        if role in ('admin', 'vice_principal', 'teacher'):
            links.append('<a data-school-records-nav="1" href="/administration/teacher-records/curriculum/" class="nav-link"><i class="bi bi-journal-check"></i> متابعة ما قطع من المنهاج</a>')
            links.append('<a data-school-records-nav="1" href="/administration/teacher-records/training/" class="nav-link"><i class="bi bi-mortarboard"></i> سجل الدورات</a>')
        if links:
            html = html.replace(marker, marker + ''.join(links), 1)
            response.content = html.encode(response.charset or 'utf-8')
            if response.has_header('Content-Length'):
                response['Content-Length'] = str(len(response.content))
        return response
