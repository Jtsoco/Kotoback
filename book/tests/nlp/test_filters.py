from django.test import SimpleTestCase

from book.nlp.filters import (
    build_candidate_filter,
    compile_filter_sets,
    compile_filter_sets_for_selection,
    load_ja_common_6000_filter,
    load_ja_common_10000_filter,
    load_en_common_2k_filter,
    load_en_common_4k_filter,
    load_en_common_6k_filter,
    load_en_common_8k_filter,
    load_en_common_10k_filter,
    load_newspaper_kanji_filter,
    passes_kanji_filter,
)


class FilterLayerTests(SimpleTestCase):
    def setUp(self):
        load_ja_common_6000_filter.cache_clear()
        load_ja_common_10000_filter.cache_clear()
        load_en_common_2k_filter.cache_clear()
        load_en_common_4k_filter.cache_clear()
        load_en_common_6k_filter.cache_clear()
        load_en_common_8k_filter.cache_clear()
        load_en_common_10k_filter.cache_clear()
        load_newspaper_kanji_filter.cache_clear()
        compile_filter_sets.cache_clear()

    def test_compile_6000_without_kanji_returns_expected_sets(self):
        word_filter, kanji_filter = compile_filter_sets(
            filter_class="common_japanese",
            common_words="6k",
            include_newspaper_kanji=False,
        )

        self.assertIn("それ", word_filter)
        self.assertIn("時々", word_filter)
        self.assertNotIn("躱わす", word_filter)
        self.assertIsNone(kanji_filter)

    def test_compile_10000_with_kanji_returns_expected_sets(self):
        word_filter, kanji_filter = compile_filter_sets(
            filter_class="common_japanese",
            common_words="10k",
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
            filter_class=None,
            common_words=None,
            include_newspaper_kanji=False,
        )

        self.assertEqual(word_filter, frozenset())
        self.assertIsNone(kanji_filter)

    def test_compile_for_selection_adapter(self):
        word_filter, kanji_filter = compile_filter_sets_for_selection(
            {
                "filter_class": "common_japanese",
                "common_words": "6k",
                "include_newspaper_kanji": True,
            }
        )

        self.assertIn("それ", word_filter)
        self.assertIsNotNone(kanji_filter)

    def test_compile_filter_sets_reuses_cached_result_for_same_selection(self):
        first = compile_filter_sets(
            filter_class="common_japanese",
            common_words="10k",
            include_newspaper_kanji=True,
        )
        second = compile_filter_sets(
            filter_class="common_japanese",
            common_words="10k",
            include_newspaper_kanji=True,
        )

        self.assertIs(first, second)

    def test_compile_english_2k_returns_word_filter(self):
        word_filter, kanji_filter = compile_filter_sets(
            filter_class="common_english",
            common_words="2k",
            include_newspaper_kanji=False,
        )

        self.assertIsInstance(word_filter, frozenset)
        self.assertGreater(len(word_filter), 0)
        self.assertIsNone(kanji_filter)

    def test_compile_english_6k_returns_word_filter(self):
        word_filter, kanji_filter = compile_filter_sets(
            filter_class="common_english",
            common_words="6k",
            include_newspaper_kanji=False,
        )

        self.assertIsInstance(word_filter, frozenset)
        self.assertGreater(len(word_filter), 0)
        self.assertIsNone(kanji_filter)

    def test_compile_english_10k_returns_word_filter(self):
        word_filter, kanji_filter = compile_filter_sets(
            filter_class="common_english",
            common_words="10k",
            include_newspaper_kanji=False,
        )

        self.assertIsInstance(word_filter, frozenset)
        self.assertGreater(len(word_filter), 0)
        self.assertIsNone(kanji_filter)


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


class EnglishFilterTests(SimpleTestCase):
    """Test English-specific filtering behavior."""

    def setUp(self):
        load_en_common_2k_filter.cache_clear()
        load_en_common_4k_filter.cache_clear()
        load_en_common_6k_filter.cache_clear()
        load_en_common_8k_filter.cache_clear()
        load_en_common_10k_filter.cache_clear()
        compile_filter_sets.cache_clear()

    def test_english_2k_filters_very_common_words(self):
        """Very common words like 'the', 'a', 'is' should be in 2k filter."""
        word_filter, _ = compile_filter_sets(
            filter_class="common_english",
            common_words="2k",
            include_newspaper_kanji=False,
        )

        # These are among the most common English words
        common_words = ["the", "a", "is", "and", "to", "of", "in", "that", "it"]
        for word in common_words:
            self.assertIn(
                word,
                word_filter,
                f"'{word}' should be in 2k common English words",
            )

    def test_english_filter_excludes_uncommon_words(self):
        """Uncommon/technical words should not be in common filters."""
        word_filter, _ = compile_filter_sets(
            filter_class="common_english",
            common_words="2k",
            include_newspaper_kanji=False,
        )

        # These are uncommon/technical words
        uncommon_words = [
            "philological",
            "ubiquitous",
            "colloquialism",
            "sesquipedalian",
        ]
        for word in uncommon_words:
            self.assertNotIn(
                word,
                word_filter,
                f"'{word}' should not be in 2k common English words",
            )

    def test_english_6k_tier_contains_more_words_than_2k(self):
        """6k tier should contain all 2k words plus additional intermediate words."""
        filter_2k, _ = compile_filter_sets(
            filter_class="common_english",
            common_words="2k",
            include_newspaper_kanji=False,
        )
        filter_6k, _ = compile_filter_sets(
            filter_class="common_english",
            common_words="6k",
            include_newspaper_kanji=False,
        )

        # 6k should be larger than 2k
        self.assertGreater(len(filter_6k), len(filter_2k))

        # All 2k words should be in 6k
        self.assertTrue(
            filter_2k.issubset(filter_6k),
            "All 2k words should be included in 6k tier",
        )

    def test_english_candidate_filter_with_2k_tier(self):
        """Test that candidate filter properly uses English 2k tier."""
        word_filter, _ = compile_filter_sets(
            filter_class="common_english",
            common_words="2k",
            include_newspaper_kanji=False,
        )

        keep_candidate = build_candidate_filter(
            "en",
            word_filter,
            kanji_filter=None,
        )

        bucket = {
            "base": "test",
            "total_count": 1,
            "surface_forms": set(),
            "pos_counts": {},
        }

        # Very common words should be filtered out
        self.assertFalse(
            keep_candidate("the", bucket),
            "'the' should be filtered by 2k common words",
        )

        # Moderately uncommon words should pass
        self.assertTrue(
            keep_candidate("esoteric", bucket),
            "'esoteric' should not be filtered by 2k common words",
        )
