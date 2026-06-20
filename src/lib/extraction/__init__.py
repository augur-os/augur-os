"""Document extraction library.

Migrated from skills/document-extractor/scripts/ in Track 1 of the cross-client
bundle architecture migration. The skill bundle's MCP tool surface
(skills/document-extractor/scripts/mcp/) consumes this library — the bundle no
longer hosts the library code itself.

Public API:
    extract(path, max_tier=1, allow_cloud=False) -> ExtractionResult
        Multi-tier document extraction (Markdown via MarkItDown, OCR fallback,
        LLM vision escalation). Tier is the maximum extraction effort allowed.

    detect_available_tier() -> int
        Probe-imports backends to report the highest tier the runtime supports.

    merge_llm_results(partial_markdown, results) -> str
        Merge partial-extraction Markdown with per-page LLM results.

    ExtractionResult
        Dataclass with: markdown, format, tier_used, success, errors, etc.
"""

from __future__ import annotations

from src.lib.extraction.extractor import (
    ExtractionResult,
    detect_available_tier,
    extract,
    merge_llm_results,
)
from src.lib.extraction.cloud_vision import (
    CloudVisionResult,
    run_cloud_vision_ocr,
)
from src.lib.extraction.capabilities import (
    detect_extraction_capabilities,
    get_extraction_policy,
)
from src.lib.extraction.transcription import (
    TranscriptResult,
    can_transcribe_audio,
    transcribe_audio,
)

__all__ = [
    "ExtractionResult",
    "CloudVisionResult",
    "TranscriptResult",
    "can_transcribe_audio",
    "detect_available_tier",
    "detect_extraction_capabilities",
    "extract",
    "get_extraction_policy",
    "merge_llm_results",
    "run_cloud_vision_ocr",
    "transcribe_audio",
]
