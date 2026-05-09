"""
core/celery.py
──────────────
Celery application entry point.
Loaded via:  celery -A core worker --loglevel=info
"""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("tessact_pipeline")

# Pull CELERY_* settings from Django's settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in every INSTALLED_APP
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
