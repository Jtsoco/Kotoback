from pathlib import Path
from typing import Any
from zipfile import ZipFile

from celery import shared_task
from django.utils import timezone

from .models import IngestionJob, IngestionJobStatus
from .nlp.extract import (
    _extract_chapter_text_from_zip,
    _get_rootfile_path_from_zip,
    _get_spine_content_paths_from_zip,
)
from .nlp.filters import (
    build_candidate_filter,
    compile_filter_sets_for_selection,
)
from .nlp.tokenize import (
    merge_half_candidates,
    project_candidate,
    tokenize_to_half_candidates,
)
from .nlp.types import Candidate, HalfCandidate, WordFilterSelection


class JobCancelledError(Exception):
    """Raised when a job is cancelled at a stage checkpoint."""


def _get_job(job_id: int) -> IngestionJob:
    return IngestionJob.objects.get(id=job_id)


def _set_stage(job: IngestionJob, stage: str, progress: int) -> IngestionJob:
    job.current_stage = stage
    job.progress = progress
    job.save(update_fields=["current_stage", "progress", "updated_at"])
    return job


def _set_progress(job: IngestionJob, progress: int) -> IngestionJob:
    job.progress = progress
    job.save(update_fields=["progress", "updated_at"])
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

    epub_path = Path(job.source_file.path)
    if not epub_path.exists():
        raise FileNotFoundError(f"Source EPUB does not exist: {epub_path}")

    with ZipFile(epub_path) as zf:
        rootfile_path = _get_rootfile_path_from_zip(zf)
        spine_paths = _get_spine_content_paths_from_zip(zf, rootfile_path)
        if not spine_paths:
            raise ValueError("No spine chapter paths were found in the EPUB.")

    return {
        "epub_path": str(epub_path),
        "rootfile_path": rootfile_path,
        "spine_paths": spine_paths,
        "chapter_count": len(spine_paths),
        "source_language": job.source_language,
    }


def _get_filter_selection(job: IngestionJob) -> WordFilterSelection:
    # Filter selection persistence will be wired through API/model fields.
    _ = job
    return {
        "common_japanese": None,
        "include_newspaper_kanji": False,
    }


def _stage_tokenize_and_rank(
    job: IngestionJob,
    extracted: dict[str, Any],
) -> dict[str, Any]:
    _set_stage(job, "tokenizing-and-ranking", 50)

    epub_path = extracted["epub_path"]
    spine_paths = extracted["spine_paths"]
    source_language = extracted["source_language"]
    chapter_count = extracted["chapter_count"]

    global_buckets: dict[str, HalfCandidate] = {}
    chapter_stats: list[dict[str, Any]] = []
    total_word_count = 0

    progress_floor = 50
    progress_ceiling = 70
    progress_span = max(progress_ceiling - progress_floor, 1)

    with ZipFile(epub_path) as zf:
        for chapter_index, chapter_path in enumerate(spine_paths, start=1):
            chapter_text = _extract_chapter_text_from_zip(zf, chapter_path)
            chapter_candidates = tokenize_to_half_candidates(
                chapter_text,
                source_language,
            )
            chapter_word_count, chapter_unique_words = merge_half_candidates(
                global_buckets,
                chapter_candidates,
            )
            total_word_count += chapter_word_count

            chapter_stats.append(
                {
                    "chapterIndex": chapter_index,
                    "chapterPath": chapter_path,
                    "wordCount": chapter_word_count,
                    "uniqueWords": chapter_unique_words,
                }
            )

            # Keep cancellation responsive during long chapter loops.
            job = _get_job(job.id)
            _check_cancelled(job)

            chapter_ratio = chapter_index / chapter_count
            loop_progress = progress_floor + int(chapter_ratio * progress_span)
            _set_progress(job, min(loop_progress, progress_ceiling))

    return {
        "global_buckets": global_buckets,
        "word_count": total_word_count,
        "unique_words": len(global_buckets),
        "chapter_stats": chapter_stats,
    }


def _stage_filter_candidates(
    job: IngestionJob,
    ranked: dict[str, Any],
) -> dict[str, Any]:
    _set_stage(job, "filtering-candidates", 75)

    selection = _get_filter_selection(job)
    word_filter, kanji_filter = compile_filter_sets_for_selection(selection)

    source_language = job.source_language
    global_buckets: dict[str, HalfCandidate] = ranked["global_buckets"]
    keep_candidate = build_candidate_filter(
        source_language,
        word_filter,
        kanji_filter,
    )

    filtered_candidates: list[Candidate] = []
    filtered_out_count = 0
    filtered_unique_words = 0
    filtered_word_count = 0

    for base, bucket in global_buckets.items():
        if not keep_candidate(base, bucket):
            filtered_out_count += 1
            continue

        filtered_unique_words += 1
        filtered_word_count += bucket["total_count"]
        filtered_candidates.append(project_candidate(bucket))

    filtered_candidates.sort(
        key=lambda candidate: (-candidate["count"], candidate["base"])
    )

    if job.card_count_target > 0:
        filtered_candidates = filtered_candidates[: job.card_count_target]

    return {
        "candidates": filtered_candidates,
        "word_count": ranked["word_count"],
        "unique_words": ranked["unique_words"],
        "filtered_word_count": filtered_word_count,
        "filtered_unique_words": filtered_unique_words,
        "filtered_out_count": filtered_out_count,
        "chapter_stats": ranked["chapter_stats"],
    }


def _stage_translate(
    job: IngestionJob,
    filtered: dict[str, Any],
) -> dict[str, Any]:
    _set_stage(job, "translating", 80)
    # Placeholder until translation integration is implemented.
    preview_candidates = [
        {
            "surface": candidate["surface"],
            "base": candidate["base"],
            "count": candidate["count"],
        }
        for candidate in filtered["candidates"][:20]
    ]
    return {
        "preview_candidates": preview_candidates,
    }


def _stage_finalize(
    job: IngestionJob,
    filtered: dict[str, Any],
    translated: dict[str, Any],
) -> None:
    _set_stage(job, "finalizing", 95)

    job.result_payload = {
        "candidates": filtered["candidates"],
        "previewCandidates": translated["preview_candidates"],
        "chapterStats": filtered["chapter_stats"],
        "note": "Preview generation stages are scaffolded for phase 3/4.",
    }
    job.summary = {
        "wordCount": filtered["word_count"],
        "uniqueWords": filtered["unique_words"],
        "filteredWordCount": filtered["filtered_word_count"],
        "filteredUniqueWords": filtered["filtered_unique_words"],
        "filteredOutCount": filtered["filtered_out_count"],
        "candidateCount": len(filtered["candidates"]),
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

        filtered = _stage_filter_candidates(job, ranked)
        job = _get_job(job_id)
        _check_cancelled(job)

        translated = _stage_translate(job, filtered)
        job = _get_job(job_id)
        _check_cancelled(job)

        _stage_finalize(job, filtered, translated)
    except JobCancelledError:
        job = _get_job(job_id)
        _mark_cancelled(job)
    except Exception as exc:
        job = _get_job(job_id)
        _mark_failed(job, exc)
        raise
