"""Shared NLP types for Phase 3 filter-first candidate selection."""

from __future__ import annotations

from typing import Literal, TypedDict


CommonFilterClass = Literal["common_english", "common_japanese"]
CommonWordsLevel = Literal["2k", "4k", "6k", "8k", "10k"]


class Candidate(TypedDict):
    """Final candidate payload used by downstream translation/card creation."""

    surface: str
    base: str
    pos: str
    count: int


class HalfCandidate(TypedDict):
    """Base-keyed aggregation bucket before final candidate projection."""

    base: str
    total_count: int
    surface_forms: set[str]
    pos_counts: dict[str, int]


class WordFilterSelection(TypedDict, total=False):
    """
    Internal normalized filter selection across languages.

    `filter_class` specifies the language (English or Japanese).
    `common_words` specifies the frequency tier (2k, 4k, 6k, 8k, 10k).
    `include_newspaper_kanji` is only meaningful for Japanese.
    """

    filter_class: CommonFilterClass
    common_words: CommonWordsLevel
    include_newspaper_kanji: bool


class WordFilterSelectionRequest(TypedDict, total=False):
    """Raw HTTP request shape before normalization/validation."""

    filter_class: CommonFilterClass
    common_words: CommonWordsLevel
    include_newspaper_kanji: bool


class EpubMetadata(TypedDict, total=False):
    """Extracted EPUB package metadata from OPF rootfile."""

    title: str
    authors: list[str]
    identifier: str


def normalize_filter_selection(
    request_data: WordFilterSelectionRequest,
) -> WordFilterSelection:
    """Validate request data and map to the internal selection shape."""

    filter_class = request_data.get("filter_class")
    common_words = request_data.get("common_words")
    include_newspaper_kanji = bool(
        request_data.get("include_newspaper_kanji", False)
    )

    if not filter_class:
        raise ValueError("filter_class is required.")
    if not common_words:
        raise ValueError("common_words is required.")

    selection: WordFilterSelection = {
        "filter_class": filter_class,
        "common_words": common_words,
    }
    if include_newspaper_kanji:
        selection["include_newspaper_kanji"] = include_newspaper_kanji

    return selection

"""
Ebook metadata tags are:
dc:identifier id="uid"
dc:date (represents the first publication date of this ebook)
dc:title id="title"
(title will have a property 'file-as' for ordering, and defines what it refines)
<meta property="file-as" refines="#title"> (used for sorting, typically "Lastname, Firstname")</meta>
subtitle is also possible
dc: title id="subtitle"
dc: title id="fulltitle"

dc:subject

id="subject-1" etc
properties will define things like authority, term, authority is source for category, term contains term id for subject heading

also, se:subject properties exist, broadier non-library of congress metadata

dc:desription

dc:language (uses the ietf langauge tage https://en.wikipedia.org/wiki/IETF_language_tag)

dc:source (the source of the ebook content, e.g. a URL or original publication info)

author info is in the creator block
dc:creator id="author"
more than one author has id of author-1, author-2, etc

more info exists, can be seen here
https://standardebooks.org/manual/1.0.0/9-metadata



"""
