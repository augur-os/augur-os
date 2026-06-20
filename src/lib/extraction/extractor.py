"""Core document extraction engine for document-extractor skill.

Converts files to Markdown using MarkItDown (tier 0) with optional
LLM-assisted OCR (tier 1) for scanned PDFs and images.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from html import unescape
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap — add project root and scripts dir to sys.path
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parents[3]
_scripts_dir = Path(__file__).resolve().parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from src.logging import get_entity_logger
from src.lib.extraction import audio_extractor

logger = get_entity_logger("document-extractor")


# ---------------------------------------------------------------------------
# Lazy routing wrappers — break import cycle
# ---------------------------------------------------------------------------
# extractor is imported during src.lib.extraction package init, which routing
# pulls in transitively; a top-level routing import here would cycle.
# These module-level names are kept so tests can monkeypatch them directly.


def _routing_run_ocr(*args, **kwargs):
    """Lazy wrapper: import routing at call time to avoid an import cycle.

    extractor is imported during src.lib.extraction package init, which routing
    pulls in transitively; a top-level routing import here would cycle.
    """
    from src.lib.routing import run_ocr

    return run_ocr(*args, **kwargs)


def _routing_transcribe(*args, **kwargs):
    """Lazy wrapper: import routing at call time to avoid an import cycle."""
    from src.lib.routing import transcribe

    return transcribe(*args, **kwargs)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AI_CLIENT_ENV_VARS = [
    "CLAUDE_CODE_ENTRY_POINT",
    "CODEX_SESSION",
    "GEMINI_SESSION",
    "AUGUR_AGENT_SESSION",
]

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
    ".heic",
    ".heif",
    ".svg",
}
PDF_EXTENSIONS = {".pdf"}
OCR_PLACEHOLDER = "[Image: page requires OCR]"
PDF_OCR_RENDER_DPI = 300
PDF_OCR_MAX_IMAGE_EDGE = 512
PDF_OCR_TRIM_THRESHOLD = 12
PDF_OCR_TRIM_PADDING = 80


# ---------------------------------------------------------------------------
# ExtractionResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExtractionResult:
    """Result of a document extraction operation."""

    success: bool
    markdown: str
    title: str
    tier_used: int
    format: str
    size_bytes: int
    extraction_time: float
    ocr_applied: bool
    needs_llm: bool = False
    llm_requests: list[dict] | None = None
    partial_markdown: str | None = None
    error: str | None = None
    cloud_used: bool = False
    local_agent_used: bool = False
    escalation_reason: str | None = None
    cloud_provider: str | None = None
    cloud_model: str | None = None
    hardware_backend: str = "local"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_ai_client_context() -> bool:
    """Check if we are running inside an AI client session."""
    return any(os.environ.get(var) for var in AI_CLIENT_ENV_VARS)


def detect_available_tier() -> int:
    """Detect the highest extraction tier available in this environment.

    Returns:
        0 — always available (MarkItDown parsing)
        1 — LLM-assisted OCR available (Ollama running or AI client context)
    """
    # Tier 0 is always available
    tier = 0

    # Check for Ollama availability
    try:
        import urllib.request

        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:  # nosec B310  # hardcoded localhost URL in Request above
            if resp.status == 200:
                tier = 1
    except Exception:
        pass

    # AI client context also enables tier 1
    if is_ai_client_context():
        tier = 1

    return tier


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

_markitdown = None


def _get_markitdown():
    global _markitdown
    if _markitdown is None:
        from markitdown import MarkItDown

        _markitdown = MarkItDown()
    return _markitdown


def _extract_without_markitdown(file_path: Path, fmt: str) -> str | None:
    """Best-effort local extraction for simple formats when MarkItDown is absent."""
    text_exts = {"", "txt", "md", "markdown", "rst", "log", "yaml", "yml", "toml", "ini"}
    if fmt in text_exts:
        return file_path.read_text(encoding="utf-8", errors="replace")

    if fmt == "csv":
        with file_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            rows = list(reader)
        return "\n".join(", ".join(cell.strip() for cell in row) for row in rows)

    if fmt == "json":
        data = json.loads(file_path.read_text(encoding="utf-8", errors="replace"))
        return json.dumps(data, indent=2, ensure_ascii=False)

    if fmt in {"html", "htm"}:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        no_scripts = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
        no_tags = re.sub(r"<[^>]+>", " ", no_scripts)
        return re.sub(r"\s+", " ", unescape(no_tags)).strip()

    return None


def _is_low_signal_text(text: str) -> bool:
    """Return True when extracted text is too weak to trust for complex sources."""
    stripped = text.strip()
    if not stripped:
        return True
    if OCR_PLACEHOLDER in stripped:
        return True

    normalized = re.sub(r"\s+", " ", stripped)
    alnum_chars = sum(char.isalnum() for char in normalized)
    meaningful_lines = [line.strip() for line in stripped.splitlines() if sum(char.isalnum() for char in line) >= 8]
    long_tokens = re.findall(r"[A-Za-z0-9]{3,}", normalized)

    if alnum_chars < 40:
        return True
    if len(meaningful_lines) < 2 and len(long_tokens) < 10:
        return True

    punctuation_chars = sum(not char.isalnum() and not char.isspace() for char in normalized)
    if alnum_chars and punctuation_chars / alnum_chars > 1.2:
        return True

    return False


def _should_escalate_to_llm(file_path: Path, text: str, max_tier: int) -> bool:
    """Escalate when the source is structurally hard and local extraction is weak."""
    if max_tier < 1:
        return False
    ext = file_path.suffix.lower()
    if ext not in IMAGE_EXTENSIONS and ext not in PDF_EXTENSIONS:
        return False
    return _is_low_signal_text(text)


def _pdf_page_images_for_llm(file_path: Path, max_pages: int = 10) -> list[bytes]:
    """Render PDF pages to PNG bytes for LLM OCR requests."""
    try:
        from pdf2image import convert_from_path  # type: ignore[import]

        images = convert_from_path(str(file_path), dpi=PDF_OCR_RENDER_DPI, first_page=1, last_page=max_pages)
        page_bytes: list[bytes] = []
        for image in images:
            image = _prepare_pdf_page_image_for_ocr(image)
            with io.BytesIO() as buffer:
                image.save(buffer, format="PNG")
                page_bytes.append(buffer.getvalue())
        return page_bytes
    except Exception as exc:
        logger.debug("PDF rendering for LLM OCR unavailable for %s: %s", file_path.name, exc)
        return []


def _prepare_pdf_page_image_for_ocr(image):
    """Trim blank margins and bound PDF page images for local GLM-OCR."""
    from PIL import Image, ImageChops

    image = image.convert("RGB")
    background = Image.new("RGB", image.size, "white")
    diff = ImageChops.difference(image, background).convert("L")
    mask = diff.point(lambda pixel: 255 if pixel > PDF_OCR_TRIM_THRESHOLD else 0)
    bbox = mask.getbbox()
    if bbox:
        left = max(0, bbox[0] - PDF_OCR_TRIM_PADDING)
        top = max(0, bbox[1] - PDF_OCR_TRIM_PADDING)
        right = min(image.width, bbox[2] + PDF_OCR_TRIM_PADDING)
        bottom = min(image.height, bbox[3] + PDF_OCR_TRIM_PADDING)
        image = image.crop((left, top, right, bottom))

    if max(image.size) > PDF_OCR_MAX_IMAGE_EDGE:
        image.thumbnail((PDF_OCR_MAX_IMAGE_EDGE, PDF_OCR_MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
    return image


def _build_llm_ocr_requests(file_path: Path, partial_markdown: str = "") -> tuple[str, list[dict[str, str]]]:
    """Build partial markdown plus LLM OCR requests for images and scanned PDFs."""
    ext = file_path.suffix.lower()

    if ext in IMAGE_EXTENSIONS:
        return (
            partial_markdown.strip() or OCR_PLACEHOLDER,
            [
                {
                    "type": "ocr",
                    "request_id": "0",
                    "image_b64": base64.b64encode(file_path.read_bytes()).decode("ascii"),
                    "prompt": "Extract all text from this image. Preserve rough reading order. Return only extracted text.",
                }
            ],
        )

    if ext in PDF_EXTENSIONS:
        page_images = _pdf_page_images_for_llm(file_path)
        if not page_images:
            return partial_markdown, []

        requests: list[dict[str, str]] = []
        placeholders: list[str] = []
        for idx, image_bytes in enumerate(page_images):
            requests.append(
                {
                    "type": "ocr",
                    "request_id": str(idx),
                    "image_b64": base64.b64encode(image_bytes).decode("ascii"),
                    "prompt": "Extract all text from this scanned document page. Preserve rough reading order and return only the extracted text.",
                }
            )
            placeholders.append(OCR_PLACEHOLDER)

        sections: list[str] = []
        if partial_markdown.strip():
            sections.append(partial_markdown.strip())
        sections.extend(placeholders)
        return "\n\n".join(sections), requests

    return partial_markdown, []


def extract(
    path: str,
    max_tier: int = 1,
    *,
    audio_model_dir: str | None = None,
    allow_cloud: bool = False,
    language_hint: str | None = None,
) -> ExtractionResult:
    """Extract a document to Markdown.

    Args:
        path: Filesystem path to the document.
        max_tier: Maximum extraction tier to use (0=parse only, 1=LLM OCR).
        audio_model_dir: Optional existing local Whisper model directory for audio.
        allow_cloud: Whether policy permits cloud vision escalation after local OCR fails.
        language_hint: Optional BCP-47-ish language hint (passed through; no special-casing — D2).

    Returns:
        ExtractionResult with the extracted Markdown or error details.
    """
    file_path = Path(path)
    fmt = file_path.suffix.lstrip(".").lower() if file_path.suffix else ""
    ext = file_path.suffix.lower()

    # Validate file exists
    if not file_path.exists():
        return ExtractionResult(
            success=False,
            markdown="",
            title=file_path.name,
            tier_used=0,
            format=fmt,
            size_bytes=0,
            extraction_time=0.0,
            ocr_applied=False,
            error=f"File not found: {path}",
        )

    size_bytes = file_path.stat().st_size
    start = time.monotonic()

    if ext in audio_extractor.AUDIO_EXTENSIONS:
        transcript = _routing_transcribe(str(file_path), model_dir=audio_model_dir)
        elapsed = time.monotonic() - start
        if transcript.success:
            return ExtractionResult(
                success=True,
                markdown=audio_extractor.format_transcript_markdown(transcript),
                title=file_path.stem,
                tier_used=0,
                format=fmt,
                size_bytes=size_bytes,
                extraction_time=elapsed,
                ocr_applied=False,
                cloud_used=transcript.cloud_used,
                hardware_backend=transcript.method,
            )
        return ExtractionResult(
            success=False,
            markdown="",
            title=file_path.name,
            tier_used=0,
            format=fmt,
            size_bytes=size_bytes,
            extraction_time=elapsed,
            ocr_applied=False,
            error=transcript.error or "transcription unavailable",
            hardware_backend=transcript.method,
        )

    # Tier 0: MarkItDown conversion
    try:
        result = _get_markitdown().convert(str(file_path))
        markdown = result.text_content or ""
        elapsed = time.monotonic() - start
    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.warning("MarkItDown conversion failed for %s: %s", path, exc)
        fallback_markdown = _extract_without_markitdown(file_path, fmt)
        if fallback_markdown is not None:
            if _should_escalate_to_llm(file_path, fallback_markdown, max_tier):
                return _request_llm_ocr(
                    file_path,
                    fmt,
                    size_bytes,
                    elapsed,
                    fallback_markdown,
                    allow_cloud=allow_cloud,
                    language_hint=language_hint,
                )
            return ExtractionResult(
                success=True,
                markdown=fallback_markdown,
                title=file_path.stem,
                tier_used=0,
                format=fmt,
                size_bytes=size_bytes,
                extraction_time=elapsed,
                ocr_applied=False,
            )
        if ext in IMAGE_EXTENSIONS and max_tier >= 1:
            return _request_llm_ocr(
                file_path,
                fmt,
                size_bytes,
                elapsed,
                "",
                allow_cloud=allow_cloud,
                language_hint=language_hint,
            )
        if ext in IMAGE_EXTENSIONS:
            return ExtractionResult(
                success=True,
                markdown="",
                title=file_path.name,
                tier_used=0,
                format=fmt,
                size_bytes=size_bytes,
                extraction_time=elapsed,
                ocr_applied=False,
            )
        return ExtractionResult(
            success=False,
            markdown="",
            title=file_path.name,
            tier_used=0,
            format=fmt,
            size_bytes=size_bytes,
            extraction_time=elapsed,
            ocr_applied=False,
            error=f"Extraction failed: {exc}",
        )

    # If we got content and it is good enough, return tier 0 result
    if markdown.strip():
        if _should_escalate_to_llm(file_path, markdown, max_tier):
            return _request_llm_ocr(
                file_path,
                fmt,
                size_bytes,
                elapsed,
                markdown,
                allow_cloud=allow_cloud,
                language_hint=language_hint,
            )
        return ExtractionResult(
            success=True,
            markdown=markdown,
            title=file_path.stem,
            tier_used=0,
            format=fmt,
            size_bytes=size_bytes,
            extraction_time=elapsed,
            ocr_applied=False,
        )

    # Empty or weak result for complex visual sources — attempt tier 1 LLM OCR
    if _should_escalate_to_llm(file_path, markdown, max_tier):
        return _request_llm_ocr(
            file_path,
            fmt,
            size_bytes,
            elapsed,
            markdown,
            allow_cloud=allow_cloud,
            language_hint=language_hint,
        )

    # Non-image with empty content — return tier 0 result
    return ExtractionResult(
        success=True,
        markdown=markdown,
        title=file_path.stem,
        tier_used=0,
        format=fmt,
        size_bytes=size_bytes,
        extraction_time=elapsed,
        ocr_applied=False,
    )


# ---------------------------------------------------------------------------
# LLM OCR (tier 1)
# ---------------------------------------------------------------------------


def _request_llm_ocr(
    file_path: Path,
    fmt: str,
    size: int,
    elapsed: float,
    partial: str,
    *,
    allow_cloud: bool,
    language_hint: str | None = None,
) -> ExtractionResult:
    """Request OCR via the routing matrix. No tiered ladder, no Hebrew special-case (D2)."""
    if language_hint:
        logger.debug("language_hint=%r ignored: routing no longer special-cases language (D2)", language_hint)
    partial_markdown, llm_requests = _build_llm_ocr_requests(file_path, partial)
    if not llm_requests:
        return ExtractionResult(
            success=True,
            markdown=partial,
            title=file_path.stem,
            tier_used=0,
            format=fmt,
            size_bytes=size,
            extraction_time=elapsed,
            ocr_applied=False,
        )

    outcome = _routing_run_ocr(llm_requests, mode=(None if allow_cloud else "offline"))

    # In-session handoff: the local AI-client session performs the OCR with its own
    # vision, so local_agent_used=True (distinct from a spawned cloud passive agent).
    if outcome.needs_handoff:
        return ExtractionResult(
            success=True,
            markdown=partial_markdown,
            title=file_path.stem,
            tier_used=1,
            format=fmt,
            size_bytes=size,
            extraction_time=elapsed,
            ocr_applied=False,
            needs_llm=True,
            llm_requests=outcome.handoff_requests,
            partial_markdown=partial_markdown,
            local_agent_used=True,
            escalation_reason="agent vision handoff",
            hardware_backend="agent-vision",
        )

    if outcome.success:
        return ExtractionResult(
            success=True,
            markdown=merge_llm_results(partial_markdown, outcome.results),
            title=file_path.stem,
            tier_used=1,
            format=fmt,
            size_bytes=size,
            extraction_time=elapsed,
            ocr_applied=True,
            hardware_backend=outcome.engine_id,
            cloud_used=(outcome.engine_id == "agent-vision"),
        )

    return ExtractionResult(
        success=False,
        markdown=partial,
        title=file_path.stem,
        tier_used=1,
        format=fmt,
        size_bytes=size,
        extraction_time=elapsed,
        ocr_applied=False,
        error=outcome.error or "OCR failed",
        escalation_reason="ocr failed",
        hardware_backend=outcome.engine_id,
    )


# ---------------------------------------------------------------------------
# Merge LLM results
# ---------------------------------------------------------------------------


def merge_llm_results(partial_markdown: str, results: dict[str, str]) -> str:
    """Merge LLM OCR results back into partial markdown.

    Replaces "[Image: page requires OCR]" placeholders with the
    corresponding OCR text from the results dict.

    Args:
        partial_markdown: Markdown containing OCR placeholders.
        results: Dict mapping placeholder index (as string) to OCR text.

    Returns:
        Merged markdown with placeholders replaced.
    """
    if not results:
        return partial_markdown

    placeholder = "[Image: page requires OCR]"
    merged = partial_markdown

    for _idx, text in results.items():
        # Replace one placeholder at a time
        merged = merged.replace(placeholder, text, 1)

    return merged
