"""core/urls.py — Root URL configuration."""
from django.contrib import admin
from django.urls import path, include

from app.core.views import DashboardHomeView, JobMonitorView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("app.core.urls")),
    path("dashboard/", DashboardHomeView.as_view(), name="dashboard-home"),
    path("dashboard/<uuid:pk>/", JobMonitorView.as_view(), name="dashboard-monitor"),
]
