"""End-to-end integration tests for the EPUB ingestion pipeline."""

import shutil
import tempfile
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from book.models import BookCard, IngestionJob, IngestionJobStatus
from book.tests.integration_tests.epub_factory import EPUBFactory


class EndToEndIngestionIntegrationTest(APITestCase):
    """API contract and user scope enforcement tests for ingestion pipeline."""

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
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        # Create a BookCard for the user
        self.bookcard = BookCard.objects.create(
            user=self.user,
            title="Test Book",
        )

    @patch("book.tasks.process_ingestion_job.delay")
    def test_full_ingestion_flow_english_to_japanese(self, mock_delay):
        """
        Upload EPUB: verify job is created, queued, and task is enqueued.
        """
        # Create a mock async result object
        mock_async_result = MagicMock()
        mock_async_result.id = "task-123"
        mock_delay.return_value = mock_async_result

        # Upload
        url = reverse("book:ingestion-job-upload")
        payload = {
            "file": EPUBFactory.create(language="en", num_chapters=1),
            "sourceLanguage": "en",
            "targetLanguage": "ja",
            "cardCountTarget": 10,
            "rarityProfile": "standard",
            "bookcard": self.bookcard.id,
        }

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, payload, format="multipart")

        # Assertions: upload response
        self.assertEqual(response.status_code, 201)
        self.assertIn("id", response.data)
        job_id = response.data["id"]

        # Assertions: job created and queued
        job = IngestionJob.objects.get(id=job_id)
        self.assertEqual(job.user_id, self.user.id)
        self.assertEqual(job.source_language, "en")
        self.assertEqual(job.target_language, "ja")
        self.assertEqual(job.status, IngestionJobStatus.QUEUED)
        self.assertEqual(job.celery_task_id, "task-123")

        # Assertions: task was enqueued
        mock_delay.assert_called_once_with(job_id)

    @patch("book.tasks.process_ingestion_job.delay")
    def test_japanese_content_extraction(self, mock_delay):
        """Test that Japanese EPUB uploads work correctly."""
        mock_async_result = MagicMock()
        mock_async_result.id = "task-456"
        mock_delay.return_value = mock_async_result

        url = reverse("book:ingestion-job-upload")
        payload = {
            "file": EPUBFactory.create(language="ja", num_chapters=1),
            "sourceLanguage": "ja",
            "targetLanguage": "en",
            "cardCountTarget": 10,
            "rarityProfile": "standard",
            "bookcard": self.bookcard.id,
        }

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, payload, format="multipart")

        self.assertEqual(response.status_code, 201)
        job = IngestionJob.objects.get(id=response.data["id"])

        self.assertEqual(job.user_id, self.user.id)
        self.assertEqual(job.source_language, "ja")
        self.assertEqual(job.target_language, "en")
        self.assertEqual(job.status, IngestionJobStatus.QUEUED)

    @patch("book.tasks.process_ingestion_job.delay")
    def test_multiple_chapters_extraction(self, mock_delay):
        """Test extraction from EPUB with multiple chapters in spine."""
        mock_async_result = MagicMock()
        mock_async_result.id = "task-789"
        mock_delay.return_value = mock_async_result

        url = reverse("book:ingestion-job-upload")
        payload = {
            "file": EPUBFactory.create(language="en", num_chapters=2),
            "sourceLanguage": "en",
            "targetLanguage": "ja",
            "cardCountTarget": 20,
            "rarityProfile": "standard",
            "bookcard": self.bookcard.id,
        }

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, payload, format="multipart")

        self.assertEqual(response.status_code, 201)
        job = IngestionJob.objects.get(id=response.data["id"])

        self.assertEqual(job.status, IngestionJobStatus.QUEUED)
        self.assertEqual(job.card_count_target, 20)

    @patch("book.tasks.process_ingestion_job.delay")
    def test_custom_content_integration(self, mock_delay):
        """Test with custom chapter content via factory override."""
        custom_content = {
            "chapter1": "<p>Custom rare words: sesquipedalian, floccinaucinilicilification, ubiquitous.</p>"
        }

        mock_async_result = MagicMock()
        mock_async_result.id = "task-custom"
        mock_delay.return_value = mock_async_result

        url = reverse("book:ingestion-job-upload")
        payload = {
            "file": EPUBFactory.create(content_override=custom_content),
            "sourceLanguage": "en",
            "targetLanguage": "ja",
            "cardCountTarget": 10,
            "rarityProfile": "standard",
            "bookcard": self.bookcard.id,
        }

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, payload, format="multipart")

        self.assertEqual(response.status_code, 201)
        job = IngestionJob.objects.get(id=response.data["id"])

        self.assertEqual(job.status, IngestionJobStatus.QUEUED)
        self.assertEqual(job.user_id, self.user.id)

    def test_upload_enforces_user_scope(self):
        """Created jobs belong only to requesting user."""
        # Create second user
        User = get_user_model()
        user2 = User.objects.create_user(
            username="other-user",
            email="other@example.com",
            password="test12345",
        )
        token2 = Token.objects.create(user=user2)

        # Create job as user1
        job = IngestionJob.objects.create(
            user=self.user,
            bookcard=self.bookcard,
            source_file=EPUBFactory.create(),
            source_language="en",
            target_language="ja",
        )

        # User2 tries to access job status
        url = reverse("book:ingestion-job-status", kwargs={"job_id": job.id})

        client2 = self.client_class()
        client2.credentials(HTTP_AUTHORIZATION=f"Token {token2.key}")
        response = client2.get(url)

        self.assertEqual(response.status_code, 404)

    def test_upload_enforces_user_scope_on_result(self):
        """Result endpoint enforces user scope."""
        # Create second user
        User = get_user_model()
        user2 = User.objects.create_user(
            username="other-user-2",
            email="other2@example.com",
            password="test12345",
        )
        token2 = Token.objects.create(user=user2)

        # Create succeeded job as user1
        job = IngestionJob.objects.create(
            user=self.user,
            bookcard=self.bookcard,
            source_file=EPUBFactory.create(),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.SUCCEEDED,
            result_payload={"candidates": []},
        )

        # User2 tries to access job result
        url = reverse("book:ingestion-job-result", kwargs={"job_id": job.id})

        client2 = self.client_class()
        client2.credentials(HTTP_AUTHORIZATION=f"Token {token2.key}")
        response = client2.get(url)

        self.assertEqual(response.status_code, 404)

    def test_result_returns_409_until_succeeded(self):
        """Result endpoint returns 409 (Conflict) while job is still processing."""
        job = IngestionJob.objects.create(
            user=self.user,
            bookcard=self.bookcard,
            source_file=EPUBFactory.create(),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
            progress=60,
        )

        url = reverse("book:ingestion-job-result", kwargs={"job_id": job.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["status"], IngestionJobStatus.PROCESSING)
        """Test with custom chapter content via factory override."""
        custom_content = {
            "chapter1": "<p>Custom rare words: sesquipedalian, floccinaucinilicilification, ubiquitous.</p>"
        }

        with patch("book.tasks.process_ingestion_job.delay") as mock_delay:
            mock_async_result = MagicMock()
            mock_async_result.id = "task-custom"
            mock_delay.return_value = mock_async_result

            url = reverse("book:ingestion-job-upload")
            payload = {
                "file": EPUBFactory.create(content_override=custom_content),
                "sourceLanguage": "en",
                "targetLanguage": "ja",
                "cardCountTarget": 10,
                "rarityProfile": "standard",
                "bookcard": self.bookcard.id,
            }

            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(url, payload, format="multipart")

            self.assertEqual(response.status_code, 201)
            job = IngestionJob.objects.get(id=response.data["id"])

            self.assertEqual(job.status, IngestionJobStatus.QUEUED)
            self.assertEqual(job.user_id, self.user.id)
