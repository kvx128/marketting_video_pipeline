"""
app/core/models.py
──────────────────
VideoJob tracks the full lifecycle of a video generation request.
UUID primary key prevents ID enumeration; status field enables
resumable workflows and cost auditing.
"""

import uuid
from django.db import models


class VideoJob(models.Model):
    """One record per video generation request."""

    class Status(models.TextChoices):
        PENDING    = "PENDING",    "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED  = "COMPLETED",  "Completed"
        FAILED     = "FAILED",     "Failed"

    # ── Identity ───────────────────────────────────────────────────────────────
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Public-safe identifier — never exposes sequential DB row IDs.",
    )
    client_name = models.CharField(max_length=255)

    # ── State machine ──────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,   # enables fast "show all PENDING jobs" queries
    )

    # ── Payload ────────────────────────────────────────────────────────────────
    xml_context = models.TextField(
        blank=True,
        help_text="DTD-validated XML context sent to Gemini (populated by worker).",
    )
    video_blueprint = models.JSONField(
        null=True,
        blank=True,
        help_text="Structured JSON plan returned by Gemini (script, shot list, etc.).",
    )
    blueprint_json = models.JSONField(null=True, blank=True)
    orchestration_time = models.FloatField(null=True, blank=True) # Seconds
    generation_time = models.FloatField(null=True, blank=True)    # Seconds
    total_time = models.FloatField(null=True, blank=True)
    video_result_url = models.URLField(
        null=True,
        blank=True,
        help_text="Final rendered video URL (populated after FFmpeg stitching).",
    )

    # ── Diagnostics ────────────────────────────────────────────────────────────
    error_log = models.TextField(
        null=True,
        blank=True,
        help_text="Full traceback or Celery retry history on failure.",
    )
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Celery task ID for external status polling.",
    )
    retry_count = models.PositiveSmallIntegerField(default=0)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name     = "Video Job"
        verbose_name_plural = "Video Jobs"

    def __str__(self) -> str:
        return f"[{self.status}] {self.client_name} ({self.id})"
