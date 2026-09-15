import gzip
import hashlib
import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


def clean_page_text(value):
    value = (value or '').replace('\x00', '').replace('\ufeff', '').replace('\ufffd', '')
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in value.splitlines()]
    return '\n'.join(line for line in lines if line).strip()


class Command(BaseCommand):
    help = 'تحويل PDF منهاج معتمد إلى حزمة JSON.GZ قابلة للاستيراد في مساعد المنهاج.'

    def add_arguments(self, parser):
        parser.add_argument('pdf', type=Path)
        parser.add_argument('--book', required=True, help='مفتاح الكتاب في ملف البيان، مثل math أو arabic')
        parser.add_argument(
            '--manifest',
            type=Path,
            default=Path('docs/curriculum_grade4_term1.json'),
            help='مسار ملف تعريف الكتب والدروس',
        )
        parser.add_argument('--output', required=True, type=Path)

    def handle(self, *args, **options):
        pdf_path = options['pdf'].resolve()
        manifest_path = options['manifest'].resolve()
        output_path = options['output'].resolve()
        if not pdf_path.is_file():
            raise CommandError(f'ملف PDF غير موجود: {pdf_path}')
        if not manifest_path.is_file():
            raise CommandError(f'ملف البيان غير موجود: {manifest_path}')
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            book = next(row for row in manifest['books'] if row['key'] == options['book'])
        except (OSError, ValueError, KeyError, StopIteration, TypeError) as exc:
            raise CommandError('تعذر قراءة تعريف الكتاب المطلوب من ملف البيان.') from exc

        try:
            import fitz
        except ImportError:
            fitz = None
        if fitz:
            document = fitz.open(str(pdf_path))
            if document.needs_pass:
                raise CommandError('ملف PDF مشفر ولا يمكن فهرسته.')
            page_count = document.page_count
            extract_page = lambda index: document[index].get_text('text')
        else:
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise CommandError('ثبّت PyMuPDF أو pypdf محليًا لتجهيز حزمة المنهاج.') from exc
            document = PdfReader(str(pdf_path))
            if document.is_encrypted:
                raise CommandError('ملف PDF مشفر ولا يمكن فهرسته.')
            page_count = len(document.pages)
            extract_page = lambda index: document.pages[index].extract_text()
        if page_count != int(book['page_count']):
            raise CommandError(
                f'عدد صفحات PDF ({page_count}) لا يطابق البيان ({book["page_count"]}). '
                'راجع إصدار الكتاب قبل الاستيراد.'
            )
        digest = hashlib.sha256()
        with pdf_path.open('rb') as pdf_file:
            for chunk in iter(lambda: pdf_file.read(1024 * 1024), b''):
                digest.update(chunk)

        offset = int(book.get('printed_page_offset') or 0)
        raw_lessons = book.get('lessons') or []
        lessons = []
        for index, row in enumerate(raw_lessons):
            start_printed = int(row['start_printed_page'])
            next_printed = (
                int(raw_lessons[index + 1]['start_printed_page'])
                if index + 1 < len(raw_lessons)
                else page_count - offset
            )
            lessons.append({
                'unit_title': row.get('unit_title', ''),
                'unit_order': int(row.get('unit_order') or 1),
                'lesson_order': index + 1,
                'title': row['title'],
                'start_printed_page': start_printed,
                'end_printed_page': next_printed - 1 if index + 1 < len(raw_lessons) else next_printed,
                'start_pdf_page': start_printed + offset,
                'end_pdf_page': (
                    next_printed + offset - 1 if index + 1 < len(raw_lessons) else page_count
                ),
            })

        pages = []
        for number in range(1, page_count + 1):
            try:
                text = clean_page_text(extract_page(number - 1))
            except Exception:
                text = ''
            printed_page = number - offset
            pages.append({
                'pdf_page_number': number,
                'printed_page_number': printed_page if printed_page > 0 else None,
                'text': text,
                'visual_summary': '',
                'needs_visual_review': len(text) < 160,
            })
            if number % 25 == 0 or number == page_count:
                self.stdout.write(f'تم استخراج {number}/{page_count} صفحة…')

        payload = {
            'schema_version': 1,
            'source': {
                'grade_level': int(book['grade_level']),
                'term': int(book['term']),
                'subject_code': book['subject_code'],
                'subject_name': book['subject_name'],
                'title': book['title'],
                'edition': book.get('edition', ''),
                'original_filename': pdf_path.name,
                'sha256': digest.hexdigest(),
                'page_count': page_count,
            },
            'lessons': lessons,
            'pages': pages,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        with output_path.open('wb') as output_file:
            with gzip.GzipFile(filename='', mode='wb', fileobj=output_file, mtime=0) as archive:
                archive.write(encoded)
        self.stdout.write(self.style.SUCCESS(
            f'تم إنشاء {output_path} — {page_count} صفحة، {len(lessons)} درسًا، SHA-256 {digest.hexdigest()}'
        ))
