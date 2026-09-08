from django.db import transaction

from .google_drive import GoogleDriveService
from .models import SchoolRadioEntry, SchoolRadioFile


RADIO_FOLDER_NAME = 'ملف الإذاعة المدرسية'


class SchoolRadioMaintenanceError(RuntimeError):
    pass


def clear_school_radio_records():
    """Clear radio records only after their dedicated Drive folder is safely handled."""
    entry_count = SchoolRadioEntry.objects.count()
    file_count = SchoolRadioFile.objects.count()
    drive_folder_deleted = False

    if file_count:
        service = GoogleDriveService()
        if not service.is_connected():
            raise SchoolRadioMaintenanceError(
                'تعذّر التفريغ لأن Google Drive غير متصل؛ أعد ربطه حتى لا تبقى ملفات الإذاعة دون سجل.'
            )
        try:
            drive_folder_deleted = service.delete_named_folder(RADIO_FOLDER_NAME)
        except Exception as exc:
            raise SchoolRadioMaintenanceError(
                'تعذّر حذف مجلد الإذاعة من Google Drive؛ لم تُحذف سجلات قاعدة البيانات.'
            ) from exc
        if not drive_folder_deleted:
            raise SchoolRadioMaintenanceError(
                'لم يُعثر على مجلد الإذاعة في Google Drive؛ لم تُحذف سجلات قاعدة البيانات لتجنب فقدان ارتباط الملفات.'
            )

    with transaction.atomic():
        SchoolRadioEntry.objects.all().delete()

    return {
        'entry_count': entry_count,
        'file_count': file_count,
        'drive_folder_deleted': drive_folder_deleted,
    }
