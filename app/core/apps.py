"""app/core/apps.py — AppConfig so Django registers the correct label."""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name           = "app.core"
    label          = "pipeline"    # avoids collision with any 'core' namespace
    verbose_name   = "Video Pipeline"
    default_auto_field = "django.db.models.BigAutoField"
