"""Phase 3 NLP package scaffolding."""

from .tokenize import (
    aggregate_doc_to_half_candidates,
    aggregate_docs_to_half_candidates,
    get_tokenizer,
    tokenize_texts_to_half_candidates,
    tokenize_to_half_candidates,
)

__all__ = [
    "extract_epub_text",
    "build_candidate_list",
    "get_tokenizer",
    "aggregate_doc_to_half_candidates",
    "aggregate_docs_to_half_candidates",
    "tokenize_to_half_candidates",
    "tokenize_texts_to_half_candidates",
]


def extract_epub_text(*args, **kwargs):
    raise NotImplementedError("EPUB extraction is not implemented yet.")


def build_candidate_list(*args, **kwargs):
    raise NotImplementedError("Candidate building is not implemented yet.")
