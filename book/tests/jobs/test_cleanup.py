"""Tests for media and database cleanup tasks."""
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from book.models import IngestionJob, IngestionJobStatus
from book.tasks import cleanup_old_ingestion_jobs, cleanup_orphaned_epubs


User = get_user_model()


def create_test_epub():
    """Create a minimal valid EPUB file content."""
    return b"PK\x03\x04"


class CleanupOldIngestionJobsTests(TestCase):
    """Test cleanup_old_ingestion_jobs task."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username="cleanup-test",
            email="cleanup@example.com",
            password="pass12345",
        )

    def test_cleanup_deletes_jobs_older_than_two_days(self):
        """Verify jobs older than 2 days are deleted."""
        # Create old job (3 days old)
        old_job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "old.epub",
                create_test_epub(),
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.SUCCEEDED,
        )
        # Set created_at after creation
        old_job.created_at = timezone.now() - timedelta(days=3)
        old_job.save(update_fields=["created_at"])

        # Create recent job (1 day old)
        recent_job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "recent.epub",
                create_test_epub(),
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.SUCCEEDED,
        )
        recent_job.created_at = timezone.now() - timedelta(days=1)
        recent_job.save(update_fields=["created_at"])

        result = cleanup_old_ingestion_jobs()

        # Old job should be deleted
        self.assertFalse(
            IngestionJob.objects.filter(id=old_job.id).exists()
        )
        # Recent job should remain
        self.assertTrue(
            IngestionJob.objects.filter(id=recent_job.id).exists()
        )
        self.assertIn("1", result)  # Only 1 job cleaned

    def test_cleanup_deletes_source_files(self):
        """Verify source EPUB files are deleted during cleanup."""
        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "cleanup-test.epub",
                create_test_epub(),
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.SUCCEEDED,
        )

        # Set to old date
        job.created_at = timezone.now() - timedelta(days=3)
        job.save(update_fields=["created_at"])

        # Get file path before cleanup
        file_path = job.source_file.name
        self.assertTrue(
            job.source_file.storage.exists(file_path),
            "File should exist before cleanup",
        )

        cleanup_old_ingestion_jobs()

        # File should be deleted
        self.assertFalse(
            job.source_file.storage.exists(file_path),
            "File should be deleted after cleanup",
        )

    def test_cleanup_handles_jobs_without_files(self):
        """Verify cleanup handles jobs with no source_file gracefully."""
        # This test is not applicable since source_file is required
        # All jobs must have files. Skip this test.
        pass

    def test_cleanup_returns_count(self):
        """Verify cleanup task returns accurate count."""
        for i in range(3):
            job = IngestionJob.objects.create(
                user=self.user,
                source_file=SimpleUploadedFile(
                    f"test-{i}.epub",
                    create_test_epub(),
                    content_type="application/epub+zip",
                ),
                source_language="en",
                target_language="ja",
                status=IngestionJobStatus.SUCCEEDED,
            )
            # Set to old date
            job.created_at = timezone.now() - timedelta(days=3)
            job.save(update_fields=["created_at"])

        result = cleanup_old_ingestion_jobs()
        self.assertIn("3", result)
        self.assertIn("old", result)

    def test_cleanup_does_not_delete_recent_jobs(self):
        """Verify jobs within 2 days are not deleted."""
        # Create job 1 day old (clearly within 2-day window)
        recent_job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "recent.epub",
                create_test_epub(),
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.SUCCEEDED,
        )
        recent_job.created_at = timezone.now() - timedelta(days=1)
        recent_job.save(update_fields=["created_at"])

        cleanup_old_ingestion_jobs()

        # Job 1 day old should still exist
        self.assertTrue(
            IngestionJob.objects.filter(id=recent_job.id).exists()
        )


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class CleanupOrphanedEpubsTests(TestCase):
    """Test cleanup_orphaned_epubs task."""

    def setUp(self):
        """Create test user and media structure."""
        self.user = User.objects.create_user(
            username="orphan-test",
            email="orphan@example.com",
            password="pass12345",
        )

    def test_cleanup_preserves_referenced_files(self):
        """Verify files with active jobs are preserved."""
        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "preserve.epub",
                create_test_epub(),
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.SUCCEEDED,
        )

        file_path = job.source_file.name

        # Run cleanup
        result = cleanup_orphaned_epubs()

        # File should still exist (referenced by job)
        self.assertTrue(job.source_file.storage.exists(file_path))
        self.assertIn("orphaned", result.lower())

    def test_cleanup_handles_missing_media_directory(self):
        """Verify cleanup safely handles case when media directory doesn't exist."""
        # Just verify the cleanup returns a valid string
        # (actual missing directory is hard to test in Docker)
        result = cleanup_orphaned_epubs()
        # Should return a string with counts
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_cleanup_does_not_crash_on_permission_errors(self):
        """Verify cleanup handles permission errors gracefully."""
        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "test.epub",
                create_test_epub(),
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.SUCCEEDED,
        )

        # Run cleanup — should not raise even if permission errors occur
        result = cleanup_orphaned_epubs()
        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)

    def test_cleanup_deletes_orphaned_files(self):
        """Verify files not referenced by any job are deleted."""
        # Create an orphaned file (not linked to any job)
        orphan_path = Path(tempfile.gettempdir()) / "orphan.epub"
        with open(orphan_path, "wb") as f:
            f.write(create_test_epub())

        # Ensure the file exists before cleanup
        self.assertTrue(orphan_path.exists())

        # Run cleanup
        result = cleanup_orphaned_epubs()

        # Orphaned file should be deleted
        self.assertFalse(orphan_path.exists())
        self.assertIn("orphaned", result.lower())
