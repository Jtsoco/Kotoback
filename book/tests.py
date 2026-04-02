import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from rest_framework import serializers

from .models import Book, BookCard, FlashCard
from .models import IngestionJob, IngestionJobStatus
from .serializers import (
    IngestionJobResultSerializer,
    IngestionJobStatusSerializer,
    IngestionJobUploadSerializer,
)
from .upload_validators import validate_epub_upload


def study_payload(word: str) -> dict:
    return {"studyWord": word, "furigana": "ふりがな"}


class DefaultViewsAndFlashcardsTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="u1",
            email="u1@example.com",
            password="pass12345",
        )
        self.user2 = User.objects.create_user(
            username="u2",
            email="u2@example.com",
            password="pass12345",
        )

        self.token = Token.objects.create(user=self.user)
        self.token2 = Token.objects.create(user=self.user2)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.book1 = Book.objects.create(title="B1")
        self.book2 = Book.objects.create(title="B2")

        self.bookcard1 = BookCard.objects.create(
            user=self.user,
            book=self.book1,
        )
        self.bookcard1.last_studied_at = timezone.now() - timedelta(days=2)
        self.bookcard1.save(update_fields=["last_studied_at"])

        self.bookcard2 = BookCard.objects.create(
            user=self.user,
            book=self.book2,
        )
        self.bookcard2.last_studied_at = timezone.now() - timedelta(days=1)
        self.bookcard2.save(update_fields=["last_studied_at"])

        self.other_bookcard = BookCard.objects.create(
            user=self.user2,
            book=self.book1,
        )

        self.flash1 = FlashCard.objects.create(
            bookcard=self.bookcard1,
            front_language="en",
            back_language="ja",
            front_data=study_payload("apple"),
            back_data=study_payload("りんご"),
        )
        self.flash2 = FlashCard.objects.create(
            bookcard=self.bookcard2,
            front_language="en",
            back_language="ja",
            front_data=study_payload("banana"),
            back_data=study_payload("バナナ"),
        )

    def test_homepage_anonymous_empty(self):
        self.client.credentials()  # remove auth
        resp = self.client.get(reverse("book:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["authenticated"], False)
        self.assertEqual(resp.data["bookcards"], [])

    def test_homepage_authenticated_orders_by_last_studied(self):
        resp = self.client.get(reverse("book:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["authenticated"], True)

        bookcards = resp.data["bookcards"]
        self.assertEqual(len(bookcards), 2)
        # bookcard2 is newer (lastStudiedAt -1 day vs -2 days)
        self.assertEqual(bookcards[0]["id"], self.bookcard2.id)
        self.assertEqual(bookcards[1]["id"], self.bookcard1.id)

        # flashcardCount should reflect each bookcard
        self.assertEqual(bookcards[0]["flashcardCount"], 1)
        self.assertEqual(bookcards[1]["flashcardCount"], 1)

    def test_flashcard_cannot_have_same_languages(self):
        url = reverse(
            "book:flashcard-list", kwargs={"bookcard_pk": self.bookcard1.id}
        )
        payload = {
            "frontLanguage": "en",
            "backLanguage": "en",
            "frontData": study_payload("apple"),
            "backData": study_payload("りんご"),
        }
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_flashcard_requires_study_word_in_both_json_blobs(self):
        url = reverse(
            "book:flashcard-list", kwargs={"bookcard_pk": self.bookcard1.id}
        )
        payload = {
            "frontLanguage": "en",
            "backLanguage": "ja",
            "frontData": {},  # missing studyWord
            "backData": study_payload("りんご"),
        }
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_flashcard_connections_enforced_user_scoping(self):
        # user1 tries to create under user2's bookcard -> should 404
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        url = reverse(
            "book:flashcard-list",
            kwargs={"bookcard_pk": self.other_bookcard.id},
        )
        payload = {
            "frontLanguage": "en",
            "backLanguage": "ja",
            "frontData": study_payload("x"),
            "backData": study_payload("y"),
        }
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_bulk_flashcard_create(self):
        url = reverse(
            "book:flashcard-list", kwargs={"bookcard_pk": self.bookcard1.id}
        )
        payload = [
            {
                "frontLanguage": "en",
                "backLanguage": "ja",
                "frontData": study_payload("c"),
                "backData": study_payload("シー"),
            },
            {
                "frontLanguage": "en",
                "backLanguage": "ja",
                "frontData": study_payload("d"),
                "backData": study_payload("ディー"),
            },
        ]
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 201)

        self.assertEqual(
            FlashCard.objects.filter(bookcard=self.bookcard1).count(),
            3,  # existing flash1 + 2 created
        )
        self.assertIn("frontLanguage", resp.data[0])
        self.assertIn("backLanguage", resp.data[0])

    def test_flashcard_crud(self):
        url = reverse(
            "book:flashcard-list", kwargs={"bookcard_pk": self.bookcard1.id}
        )
        create_payload = {
            "frontLanguage": "en",
            "backLanguage": "ja",
            "frontData": study_payload("e"),
            "backData": study_payload("イー"),
        }
        resp = self.client.post(url, create_payload, format="json")
        self.assertEqual(resp.status_code, 201)

        created_id = resp.data["id"]
        detail_url = reverse(
            "book:flashcard-detail",
            kwargs={"bookcard_pk": self.bookcard1.id, "pk": created_id},
        )

        # GET
        resp = self.client.get(detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], created_id)

        # PATCH
        patch_payload = {
            "frontLanguage": "en",
            "backLanguage": "ja",
            "frontData": study_payload("e2"),
            "backData": study_payload("イー"),
        }
        resp = self.client.patch(detail_url, patch_payload, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["frontData"]["studyWord"], "e2")

        # DELETE
        resp = self.client.delete(detail_url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(FlashCard.objects.filter(id=created_id).exists())

    # Verify response fields for bulk flashcard create.
    def test_bulk_flashcard_create_response_fields(self):
        url = reverse(
            "book:flashcard-list", kwargs={"bookcard_pk": self.bookcard1.id}
        )
        payload = [
            {
                "frontLanguage": "en",
                "backLanguage": "ja",
                "frontData": study_payload("c"),
                "backData": study_payload("シー"),
            },
            {
                "frontLanguage": "en",
                "backLanguage": "ja",
                "frontData": study_payload("d"),
                "backData": study_payload("ディー"),
            },
        ]
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            FlashCard.objects.filter(bookcard=self.bookcard1).count(),
            3,
        )
        self.assertIn("frontLanguage", resp.data[0])
        self.assertIn("backLanguage", resp.data[0])
        self.assertIn("frontData", resp.data[0])
        self.assertIn("backData", resp.data[0])
        self.assertIn("createdAt", resp.data[0])
        self.assertIn("updatedAt", resp.data[0])
        self.assertIn("id", resp.data[0])


class EpubUploadValidatorTests(APITestCase):
    def test_rejects_non_epub_extension(self):
        upload = SimpleUploadedFile(
            "not-epub.txt",
            b"hello",
            content_type="text/plain",
        )

        with self.assertRaises(serializers.ValidationError):
            validate_epub_upload(upload)

    @override_settings(EPUB_MAX_UPLOAD_SIZE=10)
    def test_rejects_when_file_exceeds_limit(self):
        upload = SimpleUploadedFile(
            "book.epub",
            b"01234567890",
            content_type="application/epub+zip",
        )

        with self.assertRaises(serializers.ValidationError):
            validate_epub_upload(upload)

    def test_accepts_valid_epub_upload(self):
        upload = SimpleUploadedFile(
            "book.epub",
            b"PK\x03\x04",
            content_type="application/epub+zip",
        )

        validated = validate_epub_upload(upload)
        self.assertEqual(validated.name, "book.epub")


class IngestionJobSerializerTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="ingestion-user",
            email="ingestion@example.com",
            password="pass12345",
        )

    def test_upload_serializer_rejects_same_source_and_target_language(self):
        serializer = IngestionJobUploadSerializer(
            data={
                "file": SimpleUploadedFile(
                    "book.epub",
                    b"PK\x03\x04",
                    content_type="application/epub+zip",
                ),
                "sourceLanguage": "en",
                "targetLanguage": "en",
                "cardCountTarget": 100,
                "rarityProfile": "standard",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_upload_serializer_accepts_valid_payload(self):
        serializer = IngestionJobUploadSerializer(
            data={
                "file": SimpleUploadedFile(
                    "book.epub",
                    b"PK\x03\x04",
                    content_type="application/epub+zip",
                ),
                "sourceLanguage": "en",
                "targetLanguage": "ja",
                "cardCountTarget": 100,
                "rarityProfile": "standard",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_status_and_result_serializers_expose_read_only_fields(self):
        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "book.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
            progress=40,
            current_stage="tokenizing",
            summary={"word_count": 1200},
            result_payload={"candidates": []},
            error_payload={},
        )

        status_data = IngestionJobStatusSerializer(job).data
        result_data = IngestionJobResultSerializer(job).data

        self.assertEqual(status_data["status"], IngestionJobStatus.PROCESSING)
        self.assertEqual(status_data["progress"], 40)
        self.assertIn("summary", status_data)
        self.assertIn("resultPayload", result_data)


class IngestionJobApiTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="ingestion-api-user",
            email="ingestion-api@example.com",
            password="pass12345",
        )
        self.user2 = User.objects.create_user(
            username="ingestion-api-user2",
            email="ingestion-api-user2@example.com",
            password="pass12345",
        )

        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    @patch("book.views.process_ingestion_job.delay")
    def test_upload_creates_job_and_enqueues_task(self, mock_delay):
        class MockAsyncResult:
            id = "task-123"

        mock_delay.return_value = MockAsyncResult()

        url = reverse("book:ingestion-job-upload")
        payload = {
            "file": SimpleUploadedFile(
                "book.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            "sourceLanguage": "en",
            "targetLanguage": "ja",
            "cardCountTarget": 100,
            "rarityProfile": "standard",
        }

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, payload, format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], IngestionJobStatus.QUEUED)
        self.assertIn("id", response.data)

        job = IngestionJob.objects.get(id=response.data["id"])
        self.assertEqual(job.user_id, self.user.id)
        self.assertEqual(job.status, IngestionJobStatus.QUEUED)
        self.assertEqual(job.celery_task_id, "task-123")

    def test_status_enforces_user_scope(self):
        job = IngestionJob.objects.create(
            user=self.user2,
            source_file=SimpleUploadedFile(
                "book.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
        )

        url = reverse("book:ingestion-job-status", kwargs={"job_id": job.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_result_returns_409_until_succeeded(self):
        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "book.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
            progress=60,
        )

        url = reverse(
            "book:ingestion-job-result", kwargs={"job_id": job.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.data["status"], IngestionJobStatus.PROCESSING
        )

    def test_cancel_marks_cancellable_job_cancelled(self):
        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "book.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.QUEUED,
        )

        url = reverse("book:ingestion-job-cancel", kwargs={"job_id": job.id})
        response = self.client.post(url, data={}, format="json")

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, IngestionJobStatus.CANCELLED)


class IngestionTaskStageTests(APITestCase):
    """Test ingestion task orchestration and stage functions."""

    def setUp(self):
        from .tasks import process_ingestion_job

        self.process_task = process_ingestion_job
        User = get_user_model()
        self.user = User.objects.create_user(
            username="task-test-user",
            email="task@example.com",
            password="pass12345",
        )

    def test_process_ingestion_job_skips_if_already_cancelled(self):
        """Verify job processing returns early if already cancelled."""
        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "book.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.CANCELLED,
        )

        # Should return without error or state change
        self.process_task(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, IngestionJobStatus.CANCELLED)

    def test_stage_extract_text_missing_file_raises_error(self):
        """Verify extraction stage handles missing EPUB file."""
        from .tasks import _stage_extract_text

        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "nonexistent.epub",
                b"",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
        )
        # Delete the file but keep the reference
        import os
        if os.path.exists(job.source_file.path):
            os.remove(job.source_file.path)

        with self.assertRaises(FileNotFoundError):
            _stage_extract_text(job)

    def test_stage_extract_text_returns_required_keys(self):
        """Verify extraction stage returns expected payload shape."""
        from .tasks import _stage_extract_text
        from zipfile import ZipFile
        import io

        # Create minimal valid EPUB structure in memory
        epub_bytes = io.BytesIO()
        with ZipFile(epub_bytes, "w") as zf:
            container_xml = (
                b"<?xml version=\"1.0\"?>\n"
                b'<container version="1.0" xmlns='
                b'"urn:oasis:names:tc:opendocument:xmlns:container">\n'
                b"  <rootfiles>\n"
                b'    <rootfile full-path="content.opf"/>\n'
                b"  </rootfiles>\n"
                b"</container>"
            )
            zf.writestr("META-INF/container.xml", container_xml)

            content_opf = (
                b"<?xml version=\"1.0\"?>\n"
                b'<package xmlns="http://www.idpf.org/2007/opf">\n'
                b"  <manifest>\n"
                b'    <item id="c1" href="ch1.xhtml"/>\n'
                b"  </manifest>\n"
                b"  <spine>\n"
                b'    <itemref idref="c1"/>\n'
                b"  </spine>\n"
                b"</package>"
            )
            zf.writestr("content.opf", content_opf)
            zf.writestr("ch1.xhtml", b"<html><body>Text</body></html>")

        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "test.epub",
                epub_bytes.getvalue(),
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
        )

        result = _stage_extract_text(job)

        self.assertIn("epub_path", result)
        self.assertIn("spine_paths", result)
        self.assertIn("chapter_count", result)
        self.assertIn("source_language", result)
        self.assertEqual(result["source_language"], "en")
        self.assertGreater(result["chapter_count"], 0)

    def test_filter_candidates_respects_card_count_target(self):
        """Verify filter stage truncates to card_count_target."""
        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "test.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            card_count_target=5,
            status=IngestionJobStatus.PROCESSING,
        )

        # Create many candidates
        global_buckets = {}
        for i in range(50):
            global_buckets[f"word{i}"] = {
                "base": f"word{i}",
                "total_count": 100 - i,
                "surface_forms": {f"word{i}"},
                "pos_counts": {"NOUN": 100 - i},
            }

        ranked = {
            "global_buckets": global_buckets,
            "word_count": 2500,
            "unique_words": 50,
            "chapter_stats": [],
        }

        from .tasks import _stage_filter_candidates

        result = _stage_filter_candidates(job, ranked)

        self.assertLessEqual(len(result["candidates"]), 5)

    def test_stage_finalize_updates_job_to_succeeded(self):
        """Verify finalize stage marks job as succeeded with payloads."""
        from .tasks import _stage_finalize

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
        self.assertIn("candidates", job.result_payload)
        self.assertIn("wordCount", job.summary)

    def test_stage_finalize_populates_summary_correctly(self):
        """Verify finalize stage creates comprehensive summary."""
        from .tasks import _stage_finalize

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
        self.assertEqual(job.summary["candidateCount"], 0)
