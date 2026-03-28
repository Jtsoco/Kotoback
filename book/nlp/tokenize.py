"""Tokenization helpers for Japanese and English candidate aggregation."""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import spacy
from spacy.language import Language as SpacyLanguage
from spacy.tokens import Doc, Token

from .types import HalfCandidate

_MODEL_BY_LANGUAGE: dict[str, str] = {
    "ja": "ja_core_news_sm",
    "en": "en_core_web_sm",
}


@lru_cache(maxsize=2)
def get_tokenizer(language: str) -> SpacyLanguage:
    """Load and cache the spaCy pipeline for the requested language code."""

    model_name = _MODEL_BY_LANGUAGE.get(language)
    if model_name is None:
        supported = ", ".join(sorted(_MODEL_BY_LANGUAGE.keys()))
        raise ValueError(
            "Unsupported language "
            f"'{language}'. Supported languages: {supported}."
        )
    return spacy.load(model_name)


def _normalize_base_form(token: Token) -> str:
    """Choose a stable base form, falling back when lemma is unavailable."""

    lemma = token.lemma_.strip()
    if lemma and lemma != "-PRON-":
        return lemma

    lower = token.lower_.strip()
    if lower:
        return lower

    return token.text.strip()


def _should_skip_token(token: Token) -> bool:
    """Exclude whitespace and punctuation from candidate aggregation."""

    return token.is_space or token.is_punct


def _update_bucket_from_doc(
    buckets: dict[str, HalfCandidate],
    doc: Doc,
) -> None:
    """Merge one tokenized doc into the shared base-keyed buckets."""

    for token in doc:
        if _should_skip_token(token):
            continue

        surface = token.text.strip()
        if not surface:
            continue

        base = _normalize_base_form(token)
        pos = token.pos_ or "X"

        bucket = buckets.get(base)
        if bucket is None:
            bucket = {
                "base": base,
                "total_count": 0,
                "surface_forms": set(),
                "pos_counts": {},
            }
            buckets[base] = bucket

        bucket["total_count"] += 1
        bucket["surface_forms"].add(surface)
        bucket["pos_counts"][pos] = bucket["pos_counts"].get(pos, 0) + 1


def aggregate_docs_to_half_candidates(
    docs: Iterable[Doc],
) -> list[HalfCandidate]:
    """Aggregate multiple docs into base-keyed HalfCandidate buckets."""

    buckets: dict[str, HalfCandidate] = {}

    for doc in docs:
        _update_bucket_from_doc(buckets, doc)

    return sorted(
        buckets.values(),
        key=lambda item: (-item["total_count"], item["base"]),
    )


def aggregate_doc_to_half_candidates(doc: Doc) -> list[HalfCandidate]:
    """Aggregate one tokenized doc into base-keyed HalfCandidate buckets."""

    return aggregate_docs_to_half_candidates([doc])


def tokenize_texts_to_half_candidates(
    texts: Iterable[str],
    language: str,
    *,
    batch_size: int = 64,
) -> list[HalfCandidate]:
    """
    Tokenize multiple texts with nlp.pipe and aggregate by base form.

    This consumes the pipe generator directly to keep memory usage stable.
    """

    tokenizer = get_tokenizer(language)
    filtered_texts = (text for text in texts if text and text.strip())
    docs = tokenizer.pipe(filtered_texts, batch_size=batch_size)
    return aggregate_docs_to_half_candidates(docs)


def tokenize_to_half_candidates(
    text: str,
    language: str,
) -> list[HalfCandidate]:
    """
    Tokenize text and aggregate tokens into base-keyed HalfCandidate entries.

    Args:
        text: Raw input text to tokenize.
        language: Language code (currently `ja` or `en`).
    """

    if not text.strip():
        return []

    return tokenize_texts_to_half_candidates([text], language=language)
