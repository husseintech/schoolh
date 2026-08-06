"""Arabic alphabetical (hija'i) sorting keys: أ ب ت ث ج ح خ د ذ ر ز س ش ص ض ط ظ ع غ ف ق ك ل م ن هـ و ي"""

_ORDER = {
    'ا': 1, 'أ': 1, 'إ': 1, 'آ': 1, 'ء': 1,
    'ب': 2, 'ت': 3, 'ث': 4, 'ج': 5, 'ح': 6, 'خ': 7,
    'د': 8, 'ذ': 9, 'ر': 10, 'ز': 11, 'س': 12, 'ش': 13,
    'ص': 14, 'ض': 15, 'ط': 16, 'ظ': 17, 'ع': 18, 'غ': 19,
    'ف': 20, 'ق': 21, 'ك': 22, 'ل': 23, 'م': 24, 'ن': 25,
    'ه': 26, 'ة': 26, 'و': 27, 'ؤ': 27, 'ي': 28, 'ى': 28, 'ئ': 28,
}


def arabic_sort_key(text):
    if not text:
        return (1,)
    key = []
    for ch in str(text).strip():
        pos = _ORDER.get(ch)
        if pos:
            key.append(pos)
        elif ch.isdigit():
            key.append(100 + int(ch))
        else:
            key.append(200 + ord(ch))
    return tuple(key)
