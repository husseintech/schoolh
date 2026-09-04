from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile, SchoolInfo
from .public_models import SchoolPublicSettings


class SchoolInfoSaveTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='school-info-admin',
            password='safe-password',
        )
        Profile.objects.create(user=self.admin, role='admin')
        self.info = SchoolInfo.objects.create(
            name_ar='الاسم القديم',
            name_en='Old School',
            principal_name='المدير القديم',
            national_number='100',
        )
        SchoolPublicSettings.objects.create(
            school_info=self.info,
            school_mobile='0590000000',
        )
        self.client.force_login(self.admin)

    def test_admin_can_update_school_info_and_mobile_without_server_error(self):
        response = self.client.post(reverse('school_info'), {
            'name_ar': 'مدرسة المنصور الأساسية',
            'name_en': 'Al Mansour Basic School',
            'principal_name': 'حسين حمامدة',
            'national_number': '200',
            'latitude': '31.4477',
            'longitude': '35.0938',
            'school_mobile': '+970599999999',
            'school_logo': '',
            'ministry_logo': '',
        })

        self.assertRedirects(response, reverse('school_info'))
        self.info.refresh_from_db()
        settings = SchoolPublicSettings.objects.get(school_info=self.info)
        self.assertEqual(self.info.name_ar, 'مدرسة المنصور الأساسية')
        self.assertEqual(self.info.principal_name, 'حسين حمامدة')
        self.assertEqual(self.info.latitude, 31.4477)
        self.assertEqual(settings.school_mobile, '+970599999999')

    def test_invalid_coordinates_return_message_without_changing_data(self):
        response = self.client.post(reverse('school_info'), {
            'name_ar': 'اسم لن يحفظ',
            'name_en': 'Invalid Coordinates',
            'principal_name': 'مدير',
            'national_number': '300',
            'latitude': '31,4477',
            'longitude': '35.0938',
            'school_mobile': '0591111111',
        })

        self.assertRedirects(response, reverse('school_info'))
        self.info.refresh_from_db()
        self.assertEqual(self.info.name_ar, 'الاسم القديم')
