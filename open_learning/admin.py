from django.contrib import admin

from .models import SchoolRadioEntry, SchoolRadioFile


class SchoolRadioFileInline(admin.TabularInline):
    model = SchoolRadioFile
    extra = 0
    readonly_fields = ('uploaded_at',)


@admin.register(SchoolRadioEntry)
class SchoolRadioEntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_date', 'category', 'ai_status', 'created_by')
    list_filter = ('category', 'ai_status', 'event_date')
    search_fields = ('title', 'topic', 'additional_presenters', 'additional_participants')
    filter_horizontal = ('presenters', 'participants')
    inlines = (SchoolRadioFileInline,)
