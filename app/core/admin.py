"""app/core/admin.py — Register VideoJob in Django admin for ops visibility."""
from django.contrib import admin
from .models import VideoJob


@admin.register(VideoJob)
class VideoJobAdmin(admin.ModelAdmin):
    list_display  = ("id", "client_name", "status", "retry_count", "created_at", "updated_at")
    list_filter   = ("status",)
    search_fields = ("client_name", "id")
    readonly_fields = (
        "id", "xml_context", "video_blueprint",
        "celery_task_id", "created_at", "updated_at",
    )
    ordering = ("-created_at",)
