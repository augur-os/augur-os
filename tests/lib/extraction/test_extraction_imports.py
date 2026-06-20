"""Smoke tests for the src.lib.extraction public API.

This test verifies the migrated library is reachable via clean Python imports,
without sys.path tricks. Functional behavior is covered by the existing
skill-side tests in skills/document-extractor/augur/tests/.
"""

from __future__ import annotations


def test_public_api_importable():
    """The four documented public symbols are importable from src.lib.extraction."""
    from src.lib.extraction import (  # noqa: F401
        ExtractionResult,
        detect_available_tier,
        extract,
        merge_llm_results,
    )


def test_public_api_origin():
    """The public symbols originate in src.lib.extraction.extractor (not the legacy skill path)."""
    from src.lib.extraction import ExtractionResult, extract

    assert (
        extract.__module__ == "src.lib.extraction.extractor"
    ), f"extract should come from src.lib.extraction.extractor; got {extract.__module__}"
    assert (
        ExtractionResult.__module__ == "src.lib.extraction.extractor"
    ), f"ExtractionResult should come from src.lib.extraction.extractor; got {ExtractionResult.__module__}"


def test_extraction_result_is_dataclass():
    """ExtractionResult is the dataclass the consumers expect (has .markdown attribute)."""
    from dataclasses import fields

    from src.lib.extraction import ExtractionResult

    field_names = {f.name for f in fields(ExtractionResult)}
    # Documented attributes consumers rely on:
    assert "markdown" in field_names, f"ExtractionResult missing 'markdown'; has {field_names}"


def test_detect_available_tier_returns_int():
    """detect_available_tier() returns an int (the highest available extraction tier)."""
    from src.lib.extraction import detect_available_tier

    tier = detect_available_tier()
    assert isinstance(tier, int), f"detect_available_tier returned {type(tier)}, expected int"
    assert tier >= 0, f"detect_available_tier returned {tier}; expected non-negative"
