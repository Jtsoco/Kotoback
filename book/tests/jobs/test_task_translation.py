from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from book.models import IngestionJob, IngestionJobStatus


class IngestionTaskTranslationTests(APITestCase):
    """Test ingestion translation stage: translation mapping, fallback."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="task-test-user",
            email="task@example.com",
            password="pass12345",
        )

    @patch("book.tasks.translate_base_words")
    def test_stage_translate_uses_translation_map(self, mock_translate):
        """Verify translation stage maps bases to translated words."""
        from book.tasks import _stage_translate

        mock_translate.return_value = {
            "book": "本",
            "dog": "犬",
        }

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
            "candidates": [
                {
                    "surface": "book",
                    "base": "book",
                    "pos": "NOUN",
                    "count": 10,
                },
                {
                    "surface": "dog",
                    "base": "dog",
                    "pos": "NOUN",
                    "count": 7,
                },
            ]
        }

        result = _stage_translate(job, filtered)

        self.assertEqual(result["translation_map"], {"book": "本", "dog": "犬"})
        self.assertEqual(result["preview_candidates"][0]["translated"], "本")
        self.assertEqual(result["preview_candidates"][1]["translated"], "犬")
        mock_translate.assert_called_once_with(
            base_words=["book", "dog"],
            source_language="en",
            target_language="ja",
        )

    @patch("book.tasks.translate_base_words")
    def test_stage_translate_falls_back_when_translation_fails(
        self,
        mock_translate,
    ):
        """Verify translation stage gracefully handles translation failures."""
        from book.tasks import _stage_translate

        mock_translate.side_effect = RuntimeError("deepl unavailable")

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
            "candidates": [
                {
                    "surface": "book",
                    "base": "book",
                    "pos": "NOUN",
                    "count": 10,
                }
            ]
        }

        result = _stage_translate(job, filtered)

        self.assertEqual(result["translation_map"], {})
        self.assertEqual(result["preview_candidates"][0]["translated"], "")
