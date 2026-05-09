"""app/core/urls.py — URL patterns for the pipeline API."""
from django.urls import path
from .views import CreateVideoJobView, VideoJobDetailView, VideoJobListView

urlpatterns = [
    # POST  /api/jobs/       → trigger new job
    # GET   /api/jobs/       → list recent jobs
    path(
        "jobs/",
        CreateVideoJobView.as_view(),   # handles POST
        name="job-create",
    ),
    path(
        "jobs/list/",
        VideoJobListView.as_view(),     # handles GET (list)
        name="job-list",
    ),
    # GET   /api/jobs/<uuid>/ → poll status
    path(
        "jobs/<uuid:job_id>/",
        VideoJobDetailView.as_view(),
        name="job-detail",
    ),
]
