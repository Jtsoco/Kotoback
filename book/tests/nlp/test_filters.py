from django.test import SimpleTestCase

from book.nlp.filters import (
    build_candidate_filter,
    compile_filter_sets,
    compile_filter_sets_for_selection,
    load_ja_common_6000_filter,
    load_ja_common_10000_filter,
    load_newspaper_kanji_filter,
    passes_kanji_filter,
    should_keep_default_candidate,
)


class FilterLayerTests(SimpleTestCase):
    def setUp(self):
        load_ja_common_6000_filter.cache_clear()
        load_ja_common_10000_filter.cache_clear()
        load_newspaper_kanji_filter.cache_clear()
        compile_filter_sets.cache_clear()

    def test_compile_6000_without_kanji_returns_expected_sets(self):
        word_filter, kanji_filter = compile_filter_sets(
            common_japanese="ja_common_6000",
            include_newspaper_kanji=False,
        )

        self.assertIn("それ", word_filter)
        self.assertIn("時々", word_filter)
        self.assertNotIn("躱わす", word_filter)
        self.assertIsNone(kanji_filter)

    def test_compile_10000_with_kanji_returns_expected_sets(self):
        word_filter, kanji_filter = compile_filter_sets(
            common_japanese="ja_common_10000",
            include_newspaper_kanji=True,
        )

        self.assertIn("一般", word_filter)
        self.assertIn("まだ", word_filter)

        self.assertIsNotNone(kanji_filter)
        assert kanji_filter is not None
        self.assertIn("日", kanji_filter)
        self.assertIn("政", kanji_filter)
        self.assertNotIn("鬱", kanji_filter)

    def test_compile_none_without_kanji_returns_empty_word_filter(self):
        word_filter, kanji_filter = compile_filter_sets(
            common_japanese=None,
            include_newspaper_kanji=False,
        )

        self.assertEqual(word_filter, frozenset())
        self.assertIsNone(kanji_filter)

    def test_compile_for_selection_adapter(self):
        word_filter, kanji_filter = compile_filter_sets_for_selection(
            {
                "common_japanese": "ja_common_6000",
                "include_newspaper_kanji": True,
            }
        )

        self.assertIn("それ", word_filter)
        self.assertIsNotNone(kanji_filter)

    def test_compile_filter_sets_reuses_cached_result_for_same_selection(self):
        first = compile_filter_sets(
            common_japanese="ja_common_10000",
            include_newspaper_kanji=True,
        )
        second = compile_filter_sets(
            common_japanese="ja_common_10000",
            include_newspaper_kanji=True,
        )

        self.assertIs(first, second)


class KanjiFilterTests(SimpleTestCase):
    """Test kanji-specific filtering logic."""

    def test_passes_kanji_filter_with_no_kanji_returns_true(self):
        word = "hello"
        filtered_kanji = frozenset()
        self.assertTrue(passes_kanji_filter(word, filtered_kanji))

    def test_passes_kanji_filter_with_all_filtered_kanji_returns_false(self):
        word = "日本"  # Both are common newspaper kanji
        filtered_kanji = frozenset(["日", "本"])
        self.assertFalse(passes_kanji_filter(word, filtered_kanji))

    def test_passes_kanji_filter_with_rare_kanji_returns_true(self):
        word = "鬱"  # Rare kanji
        filtered_kanji = frozenset()  # Empty filter
        self.assertTrue(passes_kanji_filter(word, filtered_kanji))

    def test_passes_kanji_filter_with_mixed_kanji_returns_true(
        self,
    ):
        word = "日鬱"  # One common, one rare
        filtered_kanji = frozenset(["日"])
        self.assertTrue(passes_kanji_filter(word, filtered_kanji))

    def test_passes_kanji_filter_empty_string_returns_true(self):
        word = ""
        filtered_kanji = frozenset(["日"])
        self.assertTrue(passes_kanji_filter(word, filtered_kanji))


class CandidateFilterStrategyTests(SimpleTestCase):
    """Test language-specific filter strategy builders."""

    def test_build_candidate_filter_for_japanese(self):
        word_filter = frozenset(["の", "が"])
        kanji_filter = frozenset(["日", "本"])

        keep_candidate = build_candidate_filter(
            "ja",
            word_filter,
            kanji_filter,
        )

        bucket = {
            "base": "test",
            "total_count": 1,
            "surface_forms": {"test"},
            "pos_counts": {},
        }

        # Common word should be filtered
        self.assertFalse(keep_candidate("の", bucket))

        # Rare word should pass
        self.assertTrue(keep_candidate("rare", bucket))

    def test_build_candidate_filter_for_japanese_with_no_kanji_filter(
        self,
    ):
        word_filter = frozenset(["の"])
        kanji_filter = None

        keep_candidate = build_candidate_filter(
            "ja",
            word_filter,
            kanji_filter,
        )

        bucket = {
            "base": "test",
            "total_count": 1,
            "surface_forms": set(),
            "pos_counts": {},
        }

        # Non-filtered word should pass
        self.assertTrue(keep_candidate("word", bucket))

    def test_build_candidate_filter_for_english(self):
        word_filter = frozenset(["the", "a"])
        kanji_filter = None

        keep_candidate = build_candidate_filter(
            "en",
            word_filter,
            kanji_filter,
        )

        bucket = {
            "base": "test",
            "total_count": 1,
            "surface_forms": set(),
            "pos_counts": {},
        }

        # Filtered word should be rejected
        self.assertFalse(keep_candidate("the", bucket))

        # Non-filtered word should pass
        self.assertTrue(keep_candidate("hello", bucket))

    def test_should_keep_default_candidate_always_true(self):
        bucket = {
            "base": "test",
            "total_count": 1,
            "surface_forms": set(),
            "pos_counts": {},
        }
        self.assertTrue(should_keep_default_candidate("anything", bucket))
