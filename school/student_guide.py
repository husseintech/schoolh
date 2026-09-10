from django.urls import reverse


def build_student_guide_tasks(
    *,
    student,
    can_add_survey,
    has_survey,
    unread_notifications,
    unread_messages,
    warnings_count,
    summons_count,
):
    """Build privacy-conscious guidance shown only on the student's dashboard."""
    first_name = (student.full_name or '').strip().split(' ', 1)[0] or 'عزيزي الطالب'
    tasks = []

    if can_add_survey and not has_survey:
        tasks.append({
            'key': 'survey',
            'title': 'المسح الصحي والاجتماعي',
            'message': (
                f'مرحباً {first_name}. لم تُكمل المسح الصحي والاجتماعي بعد. '
                'تعبئته بدقة تساعد المدرسة على تقديم رعاية أفضل لك، وتُعامل بياناته بسرية.'
            ),
            'action_label': 'ابدأ تعبئة المسح',
            'url': reverse('survey_form'),
            'tone': 'warning',
        })

    if unread_notifications:
        tasks.append({
            'key': 'notifications',
            'title': 'إشعارات جديدة',
            'message': (
                f'لديك إشعارات جديدة من المدرسة، وعددها {unread_notifications}. '
                'افتح صفحة الإشعارات حتى لا يفوتك أي تحديث مهم.'
            ),
            'action_label': 'عرض الإشعارات',
            'url': reverse('notification_list'),
            'tone': 'info',
        })

    if unread_messages:
        tasks.append({
            'key': 'messages',
            'title': 'رسائل تحتاج القراءة',
            'message': (
                f'لديك رسائل مدرسية غير مقروءة، وعددها {unread_messages}. '
                'راجعها لمعرفة المطلوب منك.'
            ),
            'action_label': 'فتح رسائلي',
            'url': reverse('student_messages'),
            'tone': 'info',
        })

    has_sensitive_update = bool(warnings_count or summons_count)
    has_pending_tasks = bool(tasks) or has_sensitive_update
    tasks.append({
        'key': 'student_file',
        'title': 'ملفي الطلابي' if has_pending_tasks else 'أحسنت، مهامك مكتملة',
        'message': (
            'يوجد تحديث يحتاج المتابعة في ملفك الطلابي. افتح الملف وراجعه، '
            'واستعن بولي أمرك عند الحاجة.'
            if has_sensitive_update else
            (
                'يمكنك متابعة ملفك الطلابي لمعرفة الحضور، وأذونات المغادرة، '
                'والمستوى الأكاديمي، وأحدث الملاحظات المسجلة.'
                if has_pending_tasks else
                'أحسنت، لا توجد مهام جديدة مطلوبة منك الآن. يمكنك زيارة ملفك الطلابي '
                'في أي وقت لمتابعة حضورك ومستواك الأكاديمي.'
            )
        ),
        'action_label': 'فتح ملفي',
        'url': reverse('student_detail', args=[student.id]),
        'tone': 'attention' if has_sensitive_update else 'success',
    })

    return tasks
