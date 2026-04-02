"""DeepL translation helpers for ingestion candidates."""

from __future__ import annotations

import os

import deepl

_DEEPL_LANG_BY_APP_LANG: dict[str, str] = {
    "en": "EN",
    "ja": "JA",
}


def _to_deepl_lang(language: str) -> str:
    deepl_lang = _DEEPL_LANG_BY_APP_LANG.get(language.lower())
    if not deepl_lang:
        raise ValueError(f"Unsupported language code: {language}")
    return deepl_lang


def translate_base_words(
    base_words: list[str],
    source_language: str,
    target_language: str,
) -> dict[str, str]:
    """
    Translate words in bulk and return a base->translated map.

    DeepL returns results in the same order as submitted, so mapping by
    index preserves the one-to-one source->translation relationship.
    """

    if not base_words:
        return {}

    auth_key = os.getenv("DEEPL_API_KEY", "").strip()
    if not auth_key:
        raise ValueError("DEEPL_API_KEY is not configured.")

    source_lang = _to_deepl_lang(source_language)
    target_lang = _to_deepl_lang(target_language)

    translator = deepl.Translator(auth_key)
    results = translator.translate_text(
        base_words,
        source_lang=source_lang,
        target_lang=target_lang,
    )

    if not isinstance(results, list):
        results = [results]

    translation_map: dict[str, str] = {}
    for index, translated in enumerate(results):
        if index >= len(base_words):
            break
        source_word = base_words[index]
        translation_map[source_word] = translated.text

    return translation_map
