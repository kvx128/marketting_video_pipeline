"""
app/core/views.py
──────────────────
DRF API views for the video generation pipeline.

Endpoints:
  POST /api/jobs/          → CreateVideoJobView  (triggers async pipeline)
  GET  /api/jobs/<uuid>/   → VideoJobDetailView  (polls status)
  GET  /api/jobs/          → VideoJobListView    (admin overview)
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VideoJob
from .serializers import VideoJobCreateSerializer, VideoJobStatusSerializer
from .tasks import process_video_generation

logger = logging.getLogger(__name__)


class CreateVideoJobView(APIView):
    """
    POST /api/jobs/

    Body: { "client_name": "Tessact Demo" }

    Creates a VideoJob record (PENDING) then immediately offloads processing
    to the Celery worker.  Returns 202 Accepted — the client must poll
    /api/jobs/<id>/ to track progress.
    """

    def post(self, request):
        serializer = VideoJobCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        job = VideoJob.objects.create(
            client_name=serializer.validated_data["client_name"],
        )

        # Dispatch to worker — .delay() returns immediately
        process_video_generation.delay(str(job.id))

        logger.info("VideoJob %s queued for client '%s'", job.id, job.client_name)

        return Response(
            {
                "job_id":           str(job.id),
                "status":           job.status,
                "message":          "Video generation queued. Poll the status URL for updates.",
                "check_status_url": f"/api/jobs/{job.id}/",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class VideoJobDetailView(APIView):
    """
    GET /api/jobs/<uuid>/

    Lightweight polling endpoint — returns the full job state.
    Clients should poll every 5–10 seconds until status is COMPLETED or FAILED.
    """

    def get(self, request, job_id):
        try:
            job = VideoJob.objects.get(id=job_id)
        except VideoJob.DoesNotExist:
            return Response(
                {"error": f"VideoJob '{job_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = VideoJobStatusSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)


class VideoJobListView(APIView):
    """
    GET /api/jobs/

    Returns the 50 most recent jobs (newest first).
    Useful for an admin dashboard or pipeline monitoring.
    """

    def get(self, request):
        jobs = VideoJob.objects.all()[:50]
        serializer = VideoJobStatusSerializer(jobs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


from django.views.generic import ListView, DetailView

class DashboardHomeView(ListView):
    model = VideoJob
    template_name = 'dashboard/home.html'
    context_object_name = 'jobs'
    ordering = ['-created_at']

class JobMonitorView(DetailView):
    model = VideoJob
    template_name = 'dashboard/monitor.html'
    context_object_name = 'job'

