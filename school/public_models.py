from django.db import models


class SchoolPublicSettings(models.Model):
    """Optional public-facing settings linked to the existing school record."""

    school_info = models.OneToOneField(
        'school.SchoolInfo',
        on_delete=models.CASCADE,
        related_name='public_settings',
        verbose_name='بيانات المدرسة',
    )
    school_mobile = models.CharField('رقم جوال المدرسة', max_length=30, blank=True)
    news_enabled = models.BooleanField('تفعيل شريط الأخبار', default=False)
    news_source_name = models.CharField('اسم مصدر الأخبار', max_length=120, blank=True)
    news_feed_url = models.URLField('رابط RSS/Atom للأخبار', max_length=500, blank=True)

    class Meta:
        app_label = 'school'
        verbose_name = 'إعدادات الواجهة العامة'
        verbose_name_plural = 'إعدادات الواجهة العامة'

    def __str__(self):
        return f'إعدادات الواجهة - {self.school_info.name_ar}'
