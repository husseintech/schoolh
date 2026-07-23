def validate_non_empty(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        print(f"خطأ: {field_name} لا يمكن أن يكون فارغًا.")
        return ""
    return stripped


def validate_student_id(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        print("خطأ: رقم الهوية لا يمكن أن يكون فارغًا.")
        return ""
    if not stripped.isdigit():
        print("خطأ: رقم الهوية يجب أن يحتوي على أرقام فقط.")
        return ""
    return stripped


def validate_age(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        print("خطأ: العمر لا يمكن أن يكون فارغًا.")
        return ""
    if not stripped.isdigit() or not (1 <= int(stripped) <= 120):
        print("خطأ: العمر يجب أن يكون رقمًا بين 1 و 120.")
        return ""
    return stripped
