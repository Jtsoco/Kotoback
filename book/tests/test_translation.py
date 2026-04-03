from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from book.translation import _to_deepl_lang, translate_base_words


class TranslationModuleTests(SimpleTestCase):
    def test_to_deepl_lang_maps_supported_codes(self):
        self.assertEqual(_to_deepl_lang("en"), "EN")
        self.assertEqual(_to_deepl_lang("ja"), "JA")

    def test_to_deepl_lang_raises_for_unsupported_code(self):
        with self.assertRaises(ValueError):
            _to_deepl_lang("fr")

    def test_translate_base_words_empty_input_returns_empty_map(self):
        result = translate_base_words([], "en", "ja")
        self.assertEqual(result, {})

    def test_translate_base_words_raises_when_api_key_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                translate_base_words(["book"], "en", "ja")

    @patch("book.translation.deepl.Translator")
    def test_translate_base_words_bulk_map_by_index(self, mock_translator_cls):
        mock_translator = mock_translator_cls.return_value
        mock_translator.translate_text.return_value = [
            SimpleNamespace(text="本"),
            SimpleNamespace(text="犬"),
        ]

        with patch.dict("os.environ", {"DEEPL_API_KEY": "test-key"}):
            result = translate_base_words(["book", "dog"], "en", "ja")

        self.assertEqual(result, {"book": "本", "dog": "犬"})
        mock_translator_cls.assert_called_once_with("test-key")
        mock_translator.translate_text.assert_called_once_with(
            ["book", "dog"],
            source_lang="EN",
            target_lang="JA",
        )

    @patch("book.translation.deepl.Translator")
    def test_translate_base_words_single_result_object(
        self,
        mock_translator_cls,
    ):
        mock_translator = mock_translator_cls.return_value
        mock_translator.translate_text.return_value = SimpleNamespace(text="本")

        with patch.dict("os.environ", {"DEEPL_API_KEY": "test-key"}):
            result = translate_base_words(["book"], "en", "ja")

        self.assertEqual(result, {"book": "本"})

    @patch("book.translation.deepl.Translator")
    def test_translate_base_words_ignores_overflow_results(
        self,
        mock_translator_cls,
    ):
        mock_translator = mock_translator_cls.return_value
        mock_translator.translate_text.return_value = [
            SimpleNamespace(text="本"),
            SimpleNamespace(text="犬"),
            SimpleNamespace(text="余分"),
        ]

        with patch.dict("os.environ", {"DEEPL_API_KEY": "test-key"}):
            result = translate_base_words(["book", "dog"], "en", "ja")

        self.assertEqual(result, {"book": "本", "dog": "犬"})
