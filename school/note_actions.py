from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from .models import Note


@login_required
def delete_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    is_admin = getattr(request.user.profile, 'role', '') == 'admin'
    is_owner = note.created_by_id == request.user.id
    if request.method != 'POST' or not (is_admin or is_owner):
        messages.error(request, 'ليس لديك صلاحية لحذف هذه الملاحظة')
        return redirect('note_list')
    note.delete()
    messages.success(request, 'تم حذف الملاحظة بنجاح')
    return redirect('note_list')
