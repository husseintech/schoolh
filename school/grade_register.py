import re


MIN_GRADE_REGISTER_ROWS = 35
MAX_GRADE_REGISTER_ROWS = 50
DEFAULT_GRADE_REGISTER_ROWS = 40

BOOK_TYPE_STAGE = 'stage'
BOOK_TYPE_UPPER = 'upper'
BOOK_TYPE_LABELS = {
    BOOK_TYPE_STAGE: 'المرحلة الأساسية (1–4)',
    BOOK_TYPE_UPPER: 'الأساسي العليا (5–6)',
}

GRADE_LABELS = {
    1: 'الصف الأول الأساسي',
    2: 'الصف الثاني الأساسي',
    3: 'الصف الثالث الأساسي',
    4: 'الصف الرابع الأساسي',
    5: 'الصف الخامس الأساسي',
    6: 'الصف السادس الأساسي',
}

GRADE_WORDS = (
    (1, ('الأول', 'الاول', 'الأولى', 'الاولى')),
    (2, ('الثاني', 'الثانية')),
    (3, ('الثالث', 'الثالثة')),
    (4, ('الرابع', 'الرابعة')),
    (5, ('الخامس', 'الخامسة')),
    (6, ('السادس', 'السادسة')),
)

ARABIC_DIGIT_TRANSLATION = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def normalize_grade_row_count(raw_value):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_GRADE_REGISTER_ROWS
    if MIN_GRADE_REGISTER_ROWS <= value <= MAX_GRADE_REGISTER_ROWS:
        return value
    return DEFAULT_GRADE_REGISTER_ROWS


def grade_register_row_heights(row_count):
    """Return safe A4 row heights, including Chrome's print header/footer reserve."""
    row_count = normalize_grade_row_count(row_count)
    if row_count >= 47:
        # Dense registers need an extra bottom reserve. Some Chrome/printer
        # combinations reserve about 20 mm for print headers and footers even
        # though the CSS page itself is A4-sized.
        return {
            'stage': 220 / row_count,
            'upper': 216 / row_count,
        }
    return {
        'stage': 242 / row_count,
        'upper': 238 / row_count,
    }


def class_grade(class_name):
    """Extract grades 1–6 from numeric or Arabic class labels."""
    normalized = (class_name or '').strip().translate(ARABIC_DIGIT_TRANSLATION)
    numeric_match = re.search(r'(?<!\d)([1-6])(?!\d)', normalized)
    if numeric_match:
        return int(numeric_match.group(1))
    for grade, words in GRADE_WORDS:
        if any(word in normalized for word in words):
            return grade
    return None


def grade_book_type(grade):
    if grade in (1, 2, 3, 4):
        return BOOK_TYPE_STAGE
    if grade in (5, 6):
        return BOOK_TYPE_UPPER
    return None


def normalize_book_type(raw_value, available_types=()):
    if raw_value in BOOK_TYPE_LABELS:
        return raw_value
    available_types = set(available_types)
    if BOOK_TYPE_STAGE in available_types:
        return BOOK_TYPE_STAGE
    if BOOK_TYPE_UPPER in available_types:
        return BOOK_TYPE_UPPER
    return BOOK_TYPE_STAGE


def grade_label(grade, recorded_class_name):
    canonical = GRADE_LABELS.get(grade, 'الصف الأساسي')
    return f'{canonical} ({recorded_class_name})'


def build_grade_student_rows(students, row_count):
    students = list(students)
    return [
        {
            'number': index + 1,
            'name': students[index].full_name if index < len(students) else '',
        }
        for index in range(row_count)
    ]
