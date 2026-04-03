"""Full pipeline integration tests—runs with real EPUB, mocked DeepL, Celery eager mode."""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings, TransactionTestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from book.models import BookCard, IngestionJob, IngestionJobStatus, FlashCard


def get_test_epub_path(filename):
    """
    Locate test EPUB file in data/ directory.
    Path: book/tests/integration_tests/data/{filename}
    """
    base_dir = Path(__file__).parent / "data"
    return str(base_dir / filename)


# Settings for eager Celery task execution (synchronous in tests)
CELERY_EAGER_SETTINGS = {
    "CELERY_TASK_ALWAYS_EAGER": True,
    "CELERY_TASK_EAGER_PROPAGATES": True,
}


@override_settings(**CELERY_EAGER_SETTINGS)
class FullPipelineIntegrationTest(TransactionTestCase):
    """
    End-to-end pipeline test with real EPUB extraction + mocked translation.

    Verifies:
    - EPUB upload → job succeeds
    - Flashcards created with correct languages
    - BookCard linked to job
    - User scope enforced
    """

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
            username="test-user",
            email="test@example.com",
            password="test12345",
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    @patch("book.tasks.translate_base_words")
    def test_upload_english_epub_creates_flashcards_pipeline_end_to_end(
        self, mock_translate
    ):
        """
        Full pipeline test with real English EPUB:
        1. Upload EPUB
        2. Task runs immediately (eager mode)
        3. Verify: job SUCCEEDED, flashcards created, user scope enforced
        """
        # Mock translation to avoid DeepL API call
        mock_translate.return_value = {
            "serendipity": "偶然性",
            "ephemeral": "はかない",
            "luminous": "光り輝く",
            "constellations": "星座",
            "fox": "キツネ",
            "lazy": "怠惰な",
        }

        # Check test EPUB exists
        epub_path = get_test_epub_path("test-en.epub")
        if not os.path.exists(epub_path):
            self.skipTest(
                f"Test EPUB not found: {epub_path}. "
                "Add book/tests/integration_tests/data/test-en.epub to run."
            )

        # Upload
        url = reverse("book:ingestion-job-upload")
        with open(epub_path, "rb") as f:
            payload = {
                "file": f,
                "sourceLanguage": "en",
                "targetLanguage": "ja",
                "cardCountTarget": 50,
                "rarityProfile": "standard",
            }
            response = self.client.post(url, payload, format="multipart")

        # Assert: upload succeeded, job created
        self.assertEqual(response.status_code, 201)
        self.assertIn("id", response.data)
        job_id = response.data["id"]

        # Assert: job succeeded (task ran in eager mode)
        job = IngestionJob.objects.get(id=job_id)
        self.assertEqual(job.status, IngestionJobStatus.SUCCEEDED)
        self.assertEqual(job.user_id, self.user.id)
        self.assertEqual(job.source_language, "en")
        self.assertEqual(job.target_language, "ja")

        # Assert: BookCard created and linked to job
        self.assertIsNotNone(job.bookcard)
        self.assertEqual(job.bookcard.user_id, self.user.id)

        # Assert: FlashCards created
        flashcards = FlashCard.objects.filter(bookcard=job.bookcard)
        self.assertGreater(
            flashcards.count(),
            0,
            "No flashcards created; EPUB extraction/ranking may have failed",
        )

        # Assert: flashcards have correct structure
        card = flashcards.first()
        self.assertEqual(card.front_language, "en")
        self.assertEqual(card.back_language, "ja")
        self.assertIn("studyWord", card.front_data)
        self.assertIn("pos", card.front_data)

        # Assert: result payload populated
        self.assertIn("previewCandidates", job.result_payload)
        self.assertGreater(len(job.result_payload["previewCandidates"]), 0)

        # Assert: job completed_at set
        self.assertIsNotNone(job.completed_at)

    @patch("book.tasks.translate_base_words")
    def test_japanese_epub_pipeline_succeeds(self, mock_translate):
        """
        Full pipeline test with real Japanese EPUB.
        Verifies Japanese tokenization + card creation.
        """
        mock_translate.return_value = {
            "図書館": "library",
            "静か": "quiet",
            "環境": "environment",
            "読書": "reading",
        }

        # Check test EPUB exists
        epub_path = get_test_epub_path("test-ja.epub")
        if not os.path.exists(epub_path):
            self.skipTest(
                f"Test EPUB not found: {epub_path}. "
                "Add book/tests/integration_tests/data/test-ja.epub to run."
            )

        # Upload
        url = reverse("book:ingestion-job-upload")
        with open(epub_path, "rb") as f:
            payload = {
                "file": f,
                "sourceLanguage": "ja",
                "targetLanguage": "en",
                "cardCountTarget": 50,
                "rarityProfile": "standard",
            }
            response = self.client.post(url, payload, format="multipart")

        # Assert: upload succeeded
        self.assertEqual(response.status_code, 201)
        job_id = response.data["id"]

        # Assert: job succeeded
        job = IngestionJob.objects.get(id=job_id)
        self.assertEqual(job.status, IngestionJobStatus.SUCCEEDED)
        self.assertEqual(job.source_language, "ja")

        # Assert: flashcards created
        flashcards = FlashCard.objects.filter(bookcard=job.bookcard)
        self.assertGreater(flashcards.count(), 0)

        # Assert: correct language pair
        card = flashcards.first()
        self.assertEqual(card.front_language, "ja")
        self.assertEqual(card.back_language, "en")

    @patch("book.tasks.translate_base_words")
    def test_user_scope_enforced_on_pipeline_results(self, mock_translate):
        """
        Verifies user scope boundary: user2 cannot view user1's job/flashcards.
        """
        mock_translate.return_value = {"test": "テスト"}

        epub_path = get_test_epub_path("test-en.epub")
        if not os.path.exists(epub_path):
            self.skipTest(f"Test EPUB not found: {epub_path}")

        # User 1 uploads
        url = reverse("book:ingestion-job-upload")
        with open(epub_path, "rb") as f:
            payload = {
                "file": f,
                "sourceLanguage": "en",
                "targetLanguage": "ja",
                "cardCountTarget": 20,
                "rarityProfile": "standard",
            }
            response = self.client.post(url, payload, format="multipart")

        self.assertEqual(response.status_code, 201)
        job_id = response.data["id"]
        job = IngestionJob.objects.get(id=job_id)

        # User 2 tries to access job status
        User = get_user_model()
        user2 = User.objects.create_user(
            username="other-user",
            email="other@example.com",
            password="test12345",
        )
        token2 = Token.objects.create(user=user2)

        client2 = APIClient()
        client2.credentials(HTTP_AUTHORIZATION=f"Token {token2.key}")

        # Try to get job status
        status_url = reverse("book:ingestion-job-status", kwargs={"job_id": job_id})
        response = client2.get(status_url)
        self.assertEqual(response.status_code, 404)

        # Try to get job result
        result_url = reverse("book:ingestion-job-result", kwargs={"job_id": job_id})
        response = client2.get(result_url)
        self.assertEqual(response.status_code, 404)

        # User 1 can still access
        response = self.client.get(status_url)
        self.assertEqual(response.status_code, 200)
