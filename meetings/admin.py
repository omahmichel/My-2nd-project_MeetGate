from django.contrib import admin

from .models import Meeting


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = (
        "topic",
        "host",
        "start_time",
        "duration_minutes",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "start_time",
        "created_at",
    )

    search_fields = (
        "topic",
        "host__email",
        "zoom_meeting_id",
    )