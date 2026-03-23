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
    surface_counts: dict[str, int]
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
