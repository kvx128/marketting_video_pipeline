"""
app/core/serializers.py
────────────────────────
DRF serializers for VideoJob. Keeps views thin and validation centralised.
"""

from rest_framework import serializers
from .models import VideoJob


class VideoJobCreateSerializer(serializers.Serializer):
    """Validates input for POST /api/jobs/."""
    client_name = serializers.CharField(max_length=255)


class VideoJobStatusSerializer(serializers.ModelSerializer):
    """Read-only serializer for GET /api/jobs/<id>/."""
    class Meta:
        model  = VideoJob
        fields = [
            "id",
            "client_name",
            "status",
            "celery_task_id",
            "video_blueprint",
            "video_result_url",
            "error_log",
            "retry_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
