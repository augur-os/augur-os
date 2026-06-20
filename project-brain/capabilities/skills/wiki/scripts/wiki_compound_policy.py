"""Shared policy for compound wiki page generation."""
from __future__ import annotations

MIN_COMPOUND_SOURCE_COUNT = 8
TARGET_COMPOUND_SOURCE_MIN = 8
TARGET_COMPOUND_SOURCE_MAX = 15
MAX_CLUSTER_CONTEXT_SOURCES = TARGET_COMPOUND_SOURCE_MAX
THIN_PAGE_EXCEPTION_CONFIDENCE = 0.95


def target_source_count_label() -> str:
    return f"{TARGET_COMPOUND_SOURCE_MIN}-{TARGET_COMPOUND_SOURCE_MAX}"


def is_compound_source_count(source_count: int) -> bool:
    return TARGET_COMPOUND_SOURCE_MIN <= source_count <= TARGET_COMPOUND_SOURCE_MAX
