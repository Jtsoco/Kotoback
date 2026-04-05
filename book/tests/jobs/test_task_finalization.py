from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from book.models import BookCard, FlashCard, IngestionJob, IngestionJobStatus


class IngestionTaskFinalizationTests(APITestCase):
    """Test ingestion finalization: bookcard/flashcard creation, idempotency."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="task-test-user",
            email="task@example.com",
            password="pass12345",
        )

    def test_stage_finalize_updates_job_to_succeeded(self):
        """Verify finalize stage marks job as succeeded with payloads."""
        from book.tasks import _stage_finalize

        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "test.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
            current_stage="finalizing",
        )

        filtered = {
            "candidates": [
                {
                    "surface": "word1",
                    "base": "word1",
                    "pos": "NOUN",
                    "count": 100,
                },
            ],
            "word_count": 5000,
            "unique_words": 500,
            "filtered_word_count": 4000,
            "filtered_unique_words": 400,
            "filtered_out_count": 100,
            "chapter_stats": [
                {
                    "chapterIndex": 1,
                    "chapterPath": "ch1.xhtml",
                    "wordCount": 5000,
                    "uniqueWords": 500,
                }
            ],
        }

        translated = {"preview_candidates": []}

        _stage_finalize(job, filtered, translated)

        job.refresh_from_db()
        self.assertEqual(job.status, IngestionJobStatus.SUCCEEDED)
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.current_stage, "completed")
        self.assertIsNotNone(job.completed_at)
        self.assertIn("previewCandidates", job.result_payload)
        self.assertIn("wordCount", job.summary)

    def test_stage_finalize_populates_summary_correctly(self):
        """Verify finalize stage creates comprehensive summary."""
        from book.tasks import _stage_finalize

        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "test.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
        )

        filtered = {
            "candidates": [],
            "word_count": 1000,
            "unique_words": 200,
            "filtered_word_count": 850,
            "filtered_unique_words": 170,
            "filtered_out_count": 30,
            "chapter_stats": [],
        }

        translated = {"preview_candidates": []}

        _stage_finalize(job, filtered, translated)

        job.refresh_from_db()
        self.assertEqual(job.summary["wordCount"], 1000)
        self.assertEqual(job.summary["uniqueWords"], 200)
        self.assertEqual(job.summary["filteredWordCount"], 850)
        self.assertEqual(job.summary["filteredUniqueWords"], 170)
        self.assertEqual(job.summary["filteredOutCount"], 30)

    @patch("book.tasks.transaction")
    def test_finalize_creates_multiple_flashcards(self, mock_transaction):
        """Verify finalize creates all flashcards in bulk."""
        from book.tasks import _stage_finalize

        # Mock transaction context manager for simpler testing
        ctx = mock_transaction.atomic.return_value
        ctx.__enter__ = lambda s: s
        ctx.__exit__ = lambda s, *args: None

        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "test.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
        )
        # Pre-set metadata fields as they would be during extraction
        job.metadata_title = "Test Book"
        job.metadata_authors = ["Author One"]
        job.metadata_epub_id = "test-id-123"

        candidates = [
            {
                "surface": f"word{i}",
                "base": f"word{i}",
                "pos": "NOUN",
                "count": 100 - i,
            }
            for i in range(5)
        ]

        filtered = {
            "candidates": candidates,
            "word_count": 1000,
            "unique_words": 200,
            "filtered_word_count": 850,
            "filtered_unique_words": 170,
            "filtered_out_count": 30,
            "chapter_stats": [],
        }

        translation_map = {
            c["base"]: f"trans_{c['base']}" for c in candidates
        }
        translated = {
            "preview_candidates": candidates[:2],
            "translation_map": translation_map,
        }

        _stage_finalize(job, filtered, translated)

        job.refresh_from_db()
        # Verify bookcard was created
        self.assertIsNotNone(job.bookcard_id)
        # Verify all flashcards were created
        flashcard_query = FlashCard.objects.filter(bookcard=job.bookcard)
        flashcard_count = flashcard_query.count()
        self.assertEqual(flashcard_count, 5)

        # Verify payload contains translation map
        self.assertIn("translationMap", job.result_payload)
        self.assertEqual(
            job.result_payload["materializedCount"],
            5,
        )

    @patch("book.tasks.FlashCard.objects.bulk_create")
    def test_finalize_idempotent_bookcard_on_flashcard_failure(
        self, mock_bulk_create
    ):
        """Verify bookcard not created twice if flashcards fail."""
        from book.tasks import _stage_finalize

        # First create a bookcard
        bookcard = BookCard.objects.create(
            user=self.user,
            title="Existing Book",
            author=["Author"],
            epub_id="existing-id",
        )

        job = IngestionJob.objects.create(
            user=self.user,
            bookcard=bookcard,  # Job already has bookcard
            source_file=SimpleUploadedFile(
                "test.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
        )
        # Pre-set metadata (doesn't matter since bookcard already exists)
        job.metadata_title = "New Book"
        job.metadata_authors = ["New Author"]
        job.metadata_epub_id = "new-id"

        # Mock bulk_create to raise exception
        mock_bulk_create.side_effect = RuntimeError("Database error")

        candidates = [
            {
                "surface": "test",
                "base": "test",
                "pos": "NOUN",
                "count": 10,
            }
        ]

        filtered = {
            "candidates": candidates,
            "word_count": 100,
            "unique_words": 10,
            "filtered_word_count": 100,
            "filtered_unique_words": 10,
            "filtered_out_count": 0,
            "chapter_stats": [],
        }

        translated = {
            "preview_candidates": candidates,
            "translation_map": {"test": "テスト"},
        }

        # Finalize should fail but not create a new bookcard
        with self.assertRaises(RuntimeError):
            _stage_finalize(job, filtered, translated)

        # Verify only one bookcard exists
        self.assertEqual(BookCard.objects.filter(user=self.user).count(), 1)
        # Verify job is marked failed
        job.refresh_from_db()
        self.assertEqual(job.status, IngestionJobStatus.FAILED)
