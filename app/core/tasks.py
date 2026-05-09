"""
app/core/tasks.py
─────────────────
Celery tasks for the video generation pipeline.

Cost discipline:
  - xml_parser runs locally (zero cost).
  - generate_video_plan() is the ONLY Gemini call; it only fires here.
  - CELERY_TASK_ACKS_LATE = True ensures the task re-queues if the worker
    dies mid-flight rather than silently disappearing.

Retry strategy (exponential back-off):
  Attempt 1 → wait  60 s
  Attempt 2 → wait 120 s
  Attempt 3 → wait 180 s
  After max_retries: status = FAILED, error logged.
"""

import logging
import os
import time

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings

from app.services.xml_parser import md_to_xml_validated
from app.services.generator import GeminiOrchestrator

from .models import VideoJob

logger = logging.getLogger(__name__)

# ── File paths resolved from settings so Docker/local paths stay in sync ──────
_CLIENT_MD  = os.path.join(settings.DATA_DIR,     "client.md")
_PURPOSE_MD = os.path.join(settings.DATA_DIR,     "purpose.md")
_DTD_PATH   = os.path.join(settings.SERVICES_DIR, "video_context.dtd")


@shared_task(bind=True, max_retries=3, name="app.core.tasks.process_video_generation")
def process_video_generation(self, job_id: str) -> dict:
    """
    Celery task: end-to-end video pipeline for a single VideoJob.

    Stages:
      1. Parse + validate MD → XML  (local, zero cost)
      2. Call GeminiOrchestrator    (paid API call)
      3. [Prompt 3+] Asset generation & FFmpeg stitching

    Args:
        job_id: UUID string of the VideoJob to process.

    Returns:
        dict with 'status' and 'job_id' for result backend storage.
    """
    # ── Fetch the job record ──────────────────────────────────────────────────
    start_total = time.time()
    try:
        job = VideoJob.objects.get(id=job_id)
    except VideoJob.DoesNotExist:
        logger.error("process_video_generation: VideoJob %s not found — aborting.", job_id)
        return {"status": "NOT_FOUND", "job_id": job_id}

    # Store the Celery task ID for external polling (e.g. GET /api/jobs/<id>/)
    job.celery_task_id = self.request.id
    job.status = VideoJob.Status.PROCESSING
    job.save(update_fields=["celery_task_id", "status", "updated_at"])
    logger.info("VideoJob %s — PROCESSING started (Celery task %s)", job_id, self.request.id)

    try:
        # ── Stage 1: Local XML generation + DTD validation (free) ────────────
        logger.info("VideoJob %s — Stage 1: parsing Markdown to XML", job_id)
        xml_data = md_to_xml_validated(_CLIENT_MD, _PURPOSE_MD, _DTD_PATH)
        job.xml_context = xml_data
        job.save(update_fields=["xml_context", "updated_at"])

        # ── Stage 2: Gemini API call (costs tokens) ───────────────────────────
        logger.info("VideoJob %s — Stage 2: calling Gemini orchestrator", job_id)
        start_orch = time.time()
        orchestrator = GeminiOrchestrator()
        blueprint = orchestrator.get_video_blueprint(xml_data)
        job.video_blueprint = blueprint
        job.blueprint_json = blueprint
        job.orchestration_time = time.time() - start_orch
        job.save(update_fields=["video_blueprint", "blueprint_json", "orchestration_time", "updated_at"])

        # ── Stage 3: Asset Generation & Stitching (Prompt 4) ──────────────────
        from app.services.asset_manager import AssetManager
        from app.services.video_engine import VideoComposer

        logger.info("VideoJob %s — Stage 3: Asset generation (idempotent)", job_id)
        start_gen = time.time()
        manager = AssetManager(job_id)
        scene_paths = {}
        first_scene_path = None

        for i, scene in enumerate(blueprint['scenes']):
            # Style Transfer Logic: Use the first image as a style reference for the others
            if i == 0:
                path = manager.get_asset(scene['visual_prompt'])
                first_scene_path = path
            else:
                path = manager.get_asset(
                    scene['visual_prompt'], 
                    reference_image_path=first_scene_path
                )
            scene_paths[i] = path

        logger.info("VideoJob %s — Stage 4: Video composition", job_id)
        # Assemble using MoviePy
        composer = VideoComposer(blueprint, scene_paths, job_id)
        final_path = os.path.join(manager.job_path, "final_short.mp4")
        composer.assemble_video(final_path)
        
        # We store relative URL or absolute local path depending on deployment.
        # For now, just save the local path.
        job.video_result_url = final_path
        job.generation_time = time.time() - start_gen

        job.status = VideoJob.Status.COMPLETED
        job.total_time = time.time() - start_total
        job.save(update_fields=["status", "video_result_url", "generation_time", "total_time", "updated_at"])
        logger.info("VideoJob %s — COMPLETED in %.2fs", job_id, job.total_time)
        return {"status": "COMPLETED", "job_id": job_id}

    except Exception as exc:
        attempt = self.request.retries + 1
        countdown = 60 * attempt   # 60 s, 120 s, 180 s

        logger.warning(
            "VideoJob %s — attempt %d/%d failed: %s. Retrying in %ds.",
            job_id, attempt, self.max_retries + 1, exc, countdown,
        )

        try:
            # self.retry() raises Retry — it will NOT be caught as a plain Exception
            # on subsequent attempts because Celery handles it internally.
            raise self.retry(exc=exc, countdown=countdown)

        except MaxRetriesExceededError:
            # All retries exhausted — permanently mark as FAILED
            logger.error("VideoJob %s — all retries exhausted. Marking FAILED.", job_id)
            job.status    = VideoJob.Status.FAILED
            job.error_log = (
                f"Failed after {self.max_retries + 1} attempts.\n"
                f"Last error: {type(exc).__name__}: {exc}"
            )
            job.retry_count = self.max_retries + 1
            job.save(update_fields=["status", "error_log", "retry_count", "updated_at"])
            return {"status": "FAILED", "job_id": job_id}
