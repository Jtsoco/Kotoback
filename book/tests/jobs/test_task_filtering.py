from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from .models import IngestionJob, IngestionJobStatus


class IngestionTaskFilteringTests(APITestCase):
    """Test ingestion filtering stage: candidate truncation and filtering."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="task-test-user",
            email="task@example.com",
            password="pass12345",
        )

    def test_filter_candidates_respects_card_count_target(self):
        """Verify filter stage truncates to card_count_target."""
        from .tasks import _stage_filter_candidates

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

        result = _stage_filter_candidates(job, ranked)

        self.assertLessEqual(len(result["candidates"]), 5)
