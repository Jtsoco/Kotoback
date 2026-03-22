from typing import Any

from celery import shared_task
from django.utils import timezone

from .models import IngestionJob, IngestionJobStatus


class JobCancelledError(Exception):
    """Raised when a job is cancelled at a stage checkpoint."""


def _get_job(job_id: int) -> IngestionJob:
    return IngestionJob.objects.get(id=job_id)


def _set_stage(job: IngestionJob, stage: str, progress: int) -> IngestionJob:
    job.current_stage = stage
    job.progress = progress
    job.save(update_fields=["current_stage", "progress", "updated_at"])
    return job


def _set_processing(job: IngestionJob) -> IngestionJob:
    job.status = IngestionJobStatus.PROCESSING
    job.current_stage = "starting"
    job.progress = 5
    job.save(
        update_fields=["status", "current_stage", "progress", "updated_at"]
    )
    return job


def _check_cancelled(job: IngestionJob) -> None:
    if job.status == IngestionJobStatus.CANCELLED:
        raise JobCancelledError()


def _stage_extract_text(job: IngestionJob) -> dict[str, Any]:
    _set_stage(job, "extracting-text", 20)
    # Placeholder until EPUB parsing is implemented.
    return {
        "raw_text": "",
        "chunks": [],
    }


def _stage_tokenize_and_rank(
    job: IngestionJob,
    extracted: dict[str, Any],
) -> dict[str, Any]:
    _set_stage(job, "tokenizing-and-ranking", 50)
    # Placeholder until language-specific normalization/ranking is implemented.
    _ = extracted
    return {
        "candidates": [],
        "word_count": 0,
        "unique_words": 0,
    }


def _stage_translate(
    job: IngestionJob,
    ranked: dict[str, Any],
) -> dict[str, Any]:
    _set_stage(job, "translating", 80)
    # Placeholder until translation integration is implemented.
    _ = ranked
    return {
        "preview_candidates": [],
    }


def _stage_finalize(
    job: IngestionJob,
    ranked: dict[str, Any],
    translated: dict[str, Any],
) -> None:
    _set_stage(job, "finalizing", 95)

    job.result_payload = {
        "previewCandidates": translated["preview_candidates"],
        "note": "Preview generation stages are scaffolded for phase 3/4.",
    }
    job.summary = {
        "wordCount": ranked["word_count"],
        "uniqueWords": ranked["unique_words"],
    }
    job.progress = 100
    job.current_stage = "completed"
    job.status = IngestionJobStatus.SUCCEEDED
    job.completed_at = timezone.now()
    job.save(
        update_fields=[
            "result_payload",
            "summary",
            "progress",
            "current_stage",
            "status",
            "completed_at",
            "updated_at",
        ]
    )


def _mark_cancelled(job: IngestionJob) -> None:
    job.status = IngestionJobStatus.CANCELLED
    job.current_stage = "cancelled"
    job.completed_at = timezone.now()
    job.save(
        update_fields=["status", "current_stage", "completed_at", "updated_at"]
    )


def _mark_failed(job: IngestionJob, exc: Exception) -> None:
    job.status = IngestionJobStatus.FAILED
    job.error_payload = {
        "error": str(exc),
        "stage": job.current_stage,
    }
    job.completed_at = timezone.now()
    job.save(
        update_fields=[
            "status",
            "error_payload",
            "completed_at",
            "updated_at",
        ]
    )


@shared_task
def add(x, y):
    """Simple test task — returns x + y."""
    return x + y


@shared_task(bind=True)
def process_ingestion_job(self, job_id: int):
    """
    Orchestrates the ingestion pipeline through explicit stage functions.

    This is intentionally staged now so each stage can become its own Celery
    task (chain/group/chord) in later phases without rewriting the contract.
    """
    _ = self
    job = _get_job(job_id)
    if job.status == IngestionJobStatus.CANCELLED:
        return

    try:
        job = _set_processing(job)
        _check_cancelled(job)

        extracted = _stage_extract_text(job)
        job = _get_job(job_id)
        _check_cancelled(job)

        ranked = _stage_tokenize_and_rank(job, extracted)
        job = _get_job(job_id)
        _check_cancelled(job)

        translated = _stage_translate(job, ranked)
        job = _get_job(job_id)
        _check_cancelled(job)

        _stage_finalize(job, ranked, translated)
    except JobCancelledError:
        job = _get_job(job_id)
        _mark_cancelled(job)
    except Exception as exc:
        job = _get_job(job_id)
        _mark_failed(job, exc)
        raise
