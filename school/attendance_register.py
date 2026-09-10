import calendar
from datetime import date


ARABIC_WEEKDAYS = (
    'الاثنين',
    'الثلاثاء',
    'الأربعاء',
    'الخميس',
    'الجمعة',
    'السبت',
    'الأحد',
)

SCHOOL_YEAR_MONTHS = (
    (8, 'آب', 'الأول'),
    (9, 'أيلول', 'الأول'),
    (10, 'تشرين الأول', 'الأول'),
    (11, 'تشرين الثاني', 'الأول'),
    (12, 'كانون الأول', 'الأول'),
    (1, 'كانون الثاني', 'الأول'),
    (2, 'شباط', 'الثاني'),
    (3, 'آذار', 'الثاني'),
    (4, 'نيسان', 'الثاني'),
    (5, 'أيار', 'الثاني'),
    (6, 'حزيران', 'الثاني'),
)

OFFICIAL_HOLIDAYS = {
    (12, 25): 'عيد الميلاد المجيد',
    (1, 1): 'رأس السنة الميلادية',
    (1, 7): 'عيد الميلاد المجيد',
}

# The user confirmed that school did not meet during August 2026. Keeping the
# exception tied to that school year makes the August page ready for normal use
# in later years without a code change.
FULLY_SHADED_AUGUST_START_YEARS = {2026}
MIN_REGISTER_STUDENTS = 35
MAX_REGISTER_STUDENTS = 50
DEFAULT_REGISTER_STUDENTS = 47


def academic_year_start(today=None):
    today = today or date.today()
    return today.year if today.month >= 8 else today.year - 1


def normalize_start_year(raw_value, *, today=None):
    default = academic_year_start(today)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return value if 2020 <= value <= 2100 else default


def normalize_row_count(raw_value):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_REGISTER_STUDENTS
    return value if MIN_REGISTER_STUDENTS <= value <= MAX_REGISTER_STUDENTS else DEFAULT_REGISTER_STUDENTS


def build_month_page(month_number, month_name, semester, start_year, *, shade_august_fully=None):
    year = start_year if month_number >= 8 else start_year + 1
    days_in_month = calendar.monthrange(year, month_number)[1]
    default_august_shading = start_year in FULLY_SHADED_AUGUST_START_YEARS
    shade_all = month_number == 8 and (
        default_august_shading if shade_august_fully is None else shade_august_fully
    )
    days = []
    for day_number in range(1, 32):
        exists = day_number <= days_in_month
        if exists:
            current_date = date(year, month_number, day_number)
            weekday_index = current_date.weekday()
            holiday_name = OFFICIAL_HOLIDAYS.get((month_number, day_number), '')
            weekend = weekday_index in (4, 5)
            shaded = shade_all or weekend or bool(holiday_name)
            weekday_name = ARABIC_WEEKDAYS[weekday_index]
        else:
            holiday_name = ''
            weekend = False
            shaded = False
            weekday_name = ''
        days.append({
            'number': day_number if exists else '',
            'exists': exists,
            'weekday_name': weekday_name,
            'weekend': weekend,
            'holiday_name': holiday_name,
            'shaded': shaded,
        })
    return {
        'number': month_number,
        'name': month_name,
        'semester': semester,
        'year': year,
        'days_in_month': days_in_month,
        'shade_all': shade_all,
        'days': days,
    }


def build_school_year_months(start_year, *, shade_august_fully=None):
    return [
        build_month_page(
            month_number,
            month_name,
            semester,
            start_year,
            shade_august_fully=shade_august_fully,
        )
        for month_number, month_name, semester in SCHOOL_YEAR_MONTHS
    ]


def build_student_rows(students, row_count=DEFAULT_REGISTER_STUDENTS):
    students = list(students)
    return [
        {
            'number': index + 1,
            'name': students[index].full_name if index < len(students) else '',
        }
        for index in range(row_count)
    ]
