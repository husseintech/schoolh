from models.student import Student
from utils.file_manager import add_student, delete_student, update_student, search_students
from utils.validators import validate_student_id, validate_non_empty, validate_age


def _print_students(students):
    if not students:
        print("\nلا يوجد طلاب لعرضهم.")
        return
    print(f"\n{'رقم الهوية':<15} {'الاسم':<20} {'العمر':<6} {'الصف':<10} {'الهاتف':<15}")
    print("-" * 66)
    for s in students:
        print(f"{s.student_id:<15} {s.name:<20} {s.age:<6} {s.grade:<10} {s.phone:<15}")


def add_student_menu():
    print("\n--- إضافة طالب جديد ---")
    sid = validate_student_id(input("رقم الهوية: "))
    if not sid:
        return
    name = validate_non_empty(input("الاسم: "), "الاسم")
    if not name:
        return
    age = validate_age(input("العمر: "))
    if not age:
        return
    grade = validate_non_empty(input("الصف: "), "الصف")
    if not grade:
        return
    phone = validate_non_empty(input("الهاتف: "), "الهاتف")
    if not phone:
        return

    add_student(Student(sid, name, age, grade, phone))


def delete_student_menu():
    print("\n--- حذف طالب ---")
    sid = validate_student_id(input("أدخل رقم الهوية المراد حذفه: "))
    if not sid:
        return
    delete_student(sid)


def update_student_menu():
    print("\n--- تعديل بيانات طالب ---")
    sid = validate_student_id(input("أدخل رقم الهوية المراد تعديله: "))
    if not sid:
        return
    name = validate_non_empty(input("الاسم الجديد: "), "الاسم")
    if not name:
        return
    age = validate_age(input("العمر الجديد: "))
    if not age:
        return
    grade = validate_non_empty(input("الصف الجديد: "), "الصف")
    if not grade:
        return
    phone = validate_non_empty(input("الهاتف الجديد: "), "الهاتف")
    if not phone:
        return
    update_student(sid, name, age, grade, phone)


def search_student_menu():
    print("\n--- البحث عن طالب ---")
    keyword = input("أدخل الاسم أو رقم الهوية للبحث: ").strip()
    if not keyword:
        print("يرجى إدخال كلمة للبحث.")
        return
    results = search_students(keyword)
    _print_students(results)


def show_all_students_menu():
    print("\n--- عرض جميع الطلاب ---")
    from utils.file_manager import load_students
    students = load_students()
    _print_students(students)


def show_menu():
    print("\n" + "=" * 40)
    print("      نظام إدارة بيانات الطلاب")
    print("=" * 40)
    print("1. إضافة طالب")
    print("2. حذف طالب")
    print("3. تعديل بيانات طالب")
    print("4. البحث عن طالب")
    print("5. عرض جميع الطلاب")
    print("6. خروج")
    print("=" * 40)


def run():
    while True:
        show_menu()
        choice = input("اختر رقم العملية (1-6): ").strip()
        if choice == "1":
            add_student_menu()
        elif choice == "2":
            delete_student_menu()
        elif choice == "3":
            update_student_menu()
        elif choice == "4":
            search_student_menu()
        elif choice == "5":
            show_all_students_menu()
        elif choice == "6":
            print("تم الخروج من البرنامج.")
            break
        else:
            print("اختيار غير صحيح. الرجاء اختيار رقم من 1 إلى 6.")
