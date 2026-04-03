"""Shared NLP types for Phase 3 filter-first candidate selection."""

from __future__ import annotations

from typing import Literal, TypedDict


CommonJapaneseFilter = Literal["ja_common_6000", "ja_common_10000"]


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


class WordFilterSelection(TypedDict):
    """
    Internal normalized filter selection.

    `common_japanese` is mutually exclusive (6000 or 10000),
    while `include_newspaper_kanji` can be toggled independently.
    """

    common_japanese: CommonJapaneseFilter | None
    include_newspaper_kanji: bool


class WordFilterSelectionRequest(TypedDict, total=False):
    """Raw HTTP request shape before normalization/validation."""

    use_common_6000: bool
    use_common_10000: bool
    include_newspaper_kanji: bool


class EpubMetadata(TypedDict, total=False):
    """Extracted EPUB package metadata from OPF rootfile."""

    title: str
    authors: list[str]
    identifier: str


def normalize_filter_selection(
    request_data: WordFilterSelectionRequest,
) -> WordFilterSelection:
    """Validate request toggles and map to the internal selection shape."""

    use_6000 = bool(request_data.get("use_common_6000", False))
    use_10000 = bool(request_data.get("use_common_10000", False))
    include_newspaper_kanji = bool(
        request_data.get("include_newspaper_kanji", False)
    )

    if use_6000 and use_10000:
        raise ValueError(
            "Only one of use_common_6000 or use_common_10000 can be selected."
        )

    common_japanese: CommonJapaneseFilter | None = None
    if use_6000:
        common_japanese = "ja_common_6000"
    elif use_10000:
        common_japanese = "ja_common_10000"

    return {
        "common_japanese": common_japanese,
        "include_newspaper_kanji": include_newspaper_kanji,
    }

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
