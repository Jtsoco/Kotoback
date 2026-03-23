from django.test import SimpleTestCase

from book.nlp.filters import (
    compile_filter_sets,
    compile_filter_sets_for_selection,
    load_ja_common_6000_filter,
    load_ja_common_10000_filter,
    load_newspaper_kanji_filter,
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
