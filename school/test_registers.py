from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import LabRegisterEntry, LibraryLoan, Profile
class SchoolRegistersTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_user(username="register_admin",password="pass1234")
        Profile.objects.create(user=self.admin,role="admin")
        self.client.login(username="register_admin",password="pass1234")
    def test_registers_home(self):
        self.assertEqual(self.client.get(reverse("registers_home")).status_code,200)
    def test_loan_older_than_15_days_is_overdue(self):
        loan=LibraryLoan.objects.create(borrower_name="طالب اختبار",book_title="كتاب اختبار",loan_date=timezone.localdate()-timedelta(days=16),created_by=self.admin)
        self.assertEqual(self.client.get(reverse("library_register")).status_code,200)
        self.assertTrue(loan.is_overdue)
    def test_returned_book_is_not_overdue(self):
        today=timezone.localdate()
        loan=LibraryLoan.objects.create(borrower_name="مستعير",book_title="كتاب معاد",loan_date=today-timedelta(days=20),returned_date=today-timedelta(days=1),created_by=self.admin)
        self.assertFalse(loan.is_overdue)
    def test_lab_types_are_separated(self):
        LabRegisterEntry.objects.create(register_type="science",title="تجربة",created_by=self.admin)
        LabRegisterEntry.objects.create(register_type="computer",title="صيانة",created_by=self.admin)
        response=self.client.get(reverse("lab_register",args=["science"]))
        self.assertContains(response,"تجربة")
        self.assertNotContains(response,"صيانة")
