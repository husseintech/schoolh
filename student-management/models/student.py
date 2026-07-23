class Student:
    def __init__(self, student_id: str, name: str, age: str, grade: str, phone: str):
        self.student_id = student_id
        self.name = name
        self.age = age
        self.grade = grade
        self.phone = phone

    def to_dict(self) -> dict:
        return {
            "رقم الهوية": self.student_id,
            "الاسم": self.name,
            "العمر": self.age,
            "الصف": self.grade,
            "الهاتف": self.phone,
        }

    @staticmethod
    def headers() -> list:
        return ["رقم الهوية", "الاسم", "العمر", "الصف", "الهاتف"]
