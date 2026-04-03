from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from .models import IngestionJob, IngestionJobStatus
from .serializers import (
    IngestionJobResultSerializer,
    IngestionJobStatusSerializer,
    IngestionJobUploadSerializer,
)


class IngestionJobSerializerTests(APITestCase):
    """Test IngestionJob serializers: upload, status, result validation."""

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
