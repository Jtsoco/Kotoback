import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from book.models import IngestionJob, IngestionJobStatus


class IngestionJobApiTests(APITestCase):
    """Test IngestionJob API endpoints: upload, status, result, cancellation."""

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
