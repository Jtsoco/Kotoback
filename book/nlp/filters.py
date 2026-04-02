"""Word-filter loading and selection compilation for Phase 3."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .types import CommonJapaneseFilter, HalfCandidate, WordFilterSelection

_JP_FILTERS_DIR = (
    Path(__file__).resolve().parent / "word_filters" / "japanese_filters"
)

_COMMON_6000_PATH = _JP_FILTERS_DIR / "6000japanese_words.txt"
_COMMON_10000_PATH = _JP_FILTERS_DIR / "common_ja_10000.txt"
_NEWSPAPER_KANJI_PATH = _JP_FILTERS_DIR / "newspaper_kanji.txt"


def _parse_filter_lines(path: Path) -> frozenset[str]:
    """Read one token per line into a deduplicated frozen set."""

    items: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            token = line.strip()
            if token:
                items.add(token)
    return frozenset(items)


@lru_cache(maxsize=1)
def load_ja_common_6000_filter() -> frozenset[str]:
    """Load the Japanese 6000 common-word filter."""

    return _parse_filter_lines(_COMMON_6000_PATH)


@lru_cache(maxsize=1)
def load_ja_common_10000_filter() -> frozenset[str]:
    """Load the Japanese 10000 common-word filter."""

    return _parse_filter_lines(_COMMON_10000_PATH)


@lru_cache(maxsize=1)
def load_newspaper_kanji_filter() -> frozenset[str]:
    """Load the kanji filter list used for newspaper-common characters."""

    return _parse_filter_lines(_NEWSPAPER_KANJI_PATH)


@lru_cache(maxsize=4)
def compile_filter_sets(
    common_japanese: CommonJapaneseFilter | None,
    include_newspaper_kanji: bool,
) -> tuple[frozenset[str], frozenset[str] | None]:
    """
    Compile selected filters into two lookup sets.

    Returns:
        (word_filter_set, kanji_filter_set_or_none)
    """

    if common_japanese == "ja_common_6000":
        word_filter = load_ja_common_6000_filter()
    elif common_japanese == "ja_common_10000":
        word_filter = load_ja_common_10000_filter()
    else:
        word_filter = frozenset()

    kanji_filter: frozenset[str] | None = None
    if include_newspaper_kanji:
        kanji_filter = load_newspaper_kanji_filter()

    return word_filter, kanji_filter


def compile_filter_sets_for_selection(
    selection: WordFilterSelection,
) -> tuple[frozenset[str], frozenset[str] | None]:
    """Adapter for using TypedDict selection with the cached compiler."""

    return compile_filter_sets(
        common_japanese=selection["common_japanese"],
        include_newspaper_kanji=selection["include_newspaper_kanji"],
    )


def _is_kanji_char(char: str) -> bool:
    code = ord(char)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
    )


def passes_kanji_filter(base: str, filtered_kanji: frozenset[str]) -> bool:
    """
    Keep candidate only when at least one kanji is outside the filtered set.

    If all kanji in the token are in the filtered set, the token is excluded.
    """

    kanji_chars = [char for char in base if _is_kanji_char(char)]
    if not kanji_chars:
        return True
    return not all(char in filtered_kanji for char in kanji_chars)


def should_keep_default_candidate(
    base: str,
    bucket: HalfCandidate,
) -> bool:
    _ = (base, bucket)
    return True


def build_candidate_filter(
    source_language: str,
    word_filter: frozenset[str],
    kanji_filter: frozenset[str] | None,
):
    """Build a language-specific candidate predicate once per filter stage."""

    if source_language == "ja":

        def keep_japanese_candidate(base: str, bucket: HalfCandidate) -> bool:
            _ = bucket
            if base in word_filter:
                return False
            if kanji_filter is None:
                return True
            return passes_kanji_filter(base, kanji_filter)

        return keep_japanese_candidate

    # English-specific filtering strategy will be added in the next phase.
    def keep_default_candidate(base: str, bucket: HalfCandidate) -> bool:
        if base in word_filter:
            return False
        return should_keep_default_candidate(base, bucket)

    return keep_default_candidate
