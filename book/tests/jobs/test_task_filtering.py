from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from book.models import IngestionJob, IngestionJobStatus


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
        from book.tasks import _stage_filter_candidates

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
            rarity_profile={"filter_class": "common_en", "common_words": 10000},
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

    def test_filter_candidates_filters_japanese(self):
        """Verify filter stage applies Japanese-specific kanji filtering."""
        from book.tasks import _stage_filter_candidates

        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "test.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            card_count_target=10,
            rarity_profile={"filter_class": "common_japanese", "common_words": "6k", "include_newspaper_kanji": False},
            status=IngestionJobStatus.PROCESSING,
        )

        global_buckets = {
            "word1": {
                "base": "word1",
                "total_count": 100,
                "surface_forms": {"word1"},
                "pos_counts": {"NOUN": 100},
            },
            "難しい": {
                "base": "難しい",
                "total_count": 50,
                "surface_forms": {"難しい"},
                "pos_counts": {"ADJ": 50},
            },
        }

        ranked = {
            "global_buckets": global_buckets,
            "word_count": 150,
            "unique_words": 2,
            "chapter_stats": [],
        }

        result = _stage_filter_candidates(job, ranked)

        # The Japanese word should be filtered out, leaving only the English word
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["base"], "word1")

    def test_filter_sub_method_gets_correct_rarity_profile(self):
        """Verify filter stage correctly retrieves rarity profile from job."""
        from book.tasks import _get_filter_selection

        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "test.epub",
                b"PK\x03\x04",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            card_count_target=10,
            rarity_profile={"filter_class": "common_english", "common_words": "2k"},

            status=IngestionJobStatus.PROCESSING,
            )

        # global_buckets = {
        #     "word1": {
        #         "base": "word1",
        #         "total_count": 100,
        #         "surface_forms": {"word1"},
        #         "pos_counts": {"NOUN": 100},
        #     },
        # }
        selection = _get_filter_selection(job)
        self.assertEqual(selection["filter_class"], "common_english")
        self.assertEqual(selection["common_words"], "2k")
        self.assertEqual(selection["include_newspaper_kanji"], False)
