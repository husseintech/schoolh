import re


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