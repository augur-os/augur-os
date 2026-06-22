"""OCR extractor — routes documents to the correct extraction method and caches results.

Supports:
- plaintext  : read file directly (txt, md, rst, csv, tsv, log, yaml, yml, json, xml)
- html       : .html / .htm — delegate to document-extractor fallback
- text_pdf   : PDF with extractable text — pymupdf extraction
- scanned_pdf: PDF without text layer — document-extractor fallback; MLX OCR if user-installed
- image      : raster images — document-extractor fallback; MLX OCR if user-installed
- office     : docx/xlsx/pptx/odt etc. — document-extractor fallback
- unknown    : unrecognised format — returns empty text

All optional dependencies (pymupdf, document-extractor, legacy user-installed
mlx-vlm) are guarded with try/except ImportError so the module loads in any
environment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.logging import get_entity_logger

logger = get_entity_logger("lib.index.ocr_extractor")

# ---------------------------------------------------------------------------
# Optional dependency guards
# ---------------------------------------------------------------------------

try:
    import fitz as _pymupdf  # type: ignore[import]

    _HAS_PYMUPDF = True
except ImportError:
    _pymupdf = None
    _HAS_PYMUPDF = False

try:
    from src.lib.extraction import extract
except ImportError:  # pragma: no cover
    extract = None  # type: ignore[assignment]

# MLX-VLM is checked lazily inside extraction helpers
_HAS_MLX_VLM: bool | None = None  # None = not yet checked

# ---------------------------------------------------------------------------
# Transient file-read resilience under concurrent indexing
# ---------------------------------------------------------------------------
# When two indexers read the same source at once (the background daemon plus a
# manual/CLI run), or iCloud is materializing a ~/Documents file, a read can
# fail with EDEADLK ("Resource deadlock avoided"). That is transient — a short
# retry succeeds — and must never be recorded as a failed extraction.
import errno as _errno  # noqa: E402
import time as _time  # noqa: E402

_LOCK_RETRY_ATTEMPTS = 4
_LOCK_RETRY_BASE_DELAY = 0.25


def is_transient_lock_error(exc: BaseException) -> bool:
    """True for transient OS/file-lock contention worth retrying (e.g. EDEADLK)."""
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == _errno.EDEADLK:
        return True
    msg = str(exc).lower()
    return "deadlock avoided" in msg or "resource deadlock" in msg


def read_source_bytes(path: Path) -> bytes:
    """Read a file's bytes, retrying briefly on transient lock contention."""
    last: BaseException | None = None
    for attempt in range(_LOCK_RETRY_ATTEMPTS):
        try:
            return path.read_bytes()
        except OSError as exc:
            last = exc
            if is_transient_lock_error(exc) and attempt < _LOCK_RETRY_ATTEMPTS - 1:
                _time.sleep(_LOCK_RETRY_BASE_DELAY * (attempt + 1))
                continue
            raise
    raise last  # type: ignore[misc]


def _open_pdf(path: Path) -> "Any":
    """Open a PDF via pymupdf, retrying briefly on transient lock contention."""
    last: BaseException | None = None
    for attempt in range(_LOCK_RETRY_ATTEMPTS):
        try:
            return _pymupdf.open(str(path))  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 — retry transient locks, re-raise the rest
            last = exc
            if is_transient_lock_error(exc) and attempt < _LOCK_RETRY_ATTEMPTS - 1:
                _time.sleep(_LOCK_RETRY_BASE_DELAY * (attempt + 1))
                continue
            raise
    raise last  # type: ignore[misc]

# ---------------------------------------------------------------------------
# Extension maps
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
}

_OFFICE_EXTS = {
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    ".odt",
    ".ods",
    ".odp",
}

_PLAINTEXT_EXTS = {
    ".txt",
    ".md",
    ".rst",
    ".csv",
    ".tsv",
    ".log",
    ".yaml",
    ".yml",
    ".json",
    ".xml",
}

_HTML_EXTS = {".html", ".htm"}


# ---------------------------------------------------------------------------
# PDF classification helper
# ---------------------------------------------------------------------------


def _classify_pdf(path: Path) -> "tuple[str, Any]":
    """Classify a PDF as text_pdf or scanned_pdf.

    Returns (doc_type, opened_doc) where opened_doc can be reused by the
    extractor to avoid re-opening. Returns (type, None) on failure.
    """
    if not _HAS_PYMUPDF:
        return "scanned_pdf", None

    try:
        doc = _open_pdf(path)
        pages_to_check = min(3, len(doc))
        total_chars = sum(len(doc[i].get_text("text").strip()) for i in range(pages_to_check))
        doc_type = "text_pdf" if total_chars > 50 else "scanned_pdf"
        return doc_type, doc
    except Exception as exc:
        logger.warning("PDF classification failed for %s: %s", path, exc)
        return "scanned_pdf", None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_doc_type(path: Path) -> str:
    """Detect the document type of *path*.

    Returns one of:
        "image", "office", "plaintext", "html",
        "text_pdf", "scanned_pdf", "unknown"
    """
    suffix = path.suffix.lower()

    if suffix in _IMAGE_EXTS:
        return "image"
    if suffix in _OFFICE_EXTS:
        return "office"
    if suffix in _PLAINTEXT_EXTS:
        return "plaintext"
    if suffix in _HTML_EXTS:
        return "html"
    if suffix == ".pdf":
        doc_type, doc = _classify_pdf(path)
        if doc is not None:
            doc.close()
        return doc_type
    return "unknown"


def _extract_pdf(path: Path) -> dict:
    """Classify and extract a PDF in one pass, reusing the opened doc."""
    doc_type, doc = _classify_pdf(path)
    try:
        if doc_type == "text_pdf":
            return _extract_pymupdf(path, doc=doc)
        return _extract_image_ocr(path)
    finally:
        if doc is not None:
            doc.close()


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _extract_plaintext(path: Path) -> dict:
    """Read a text file directly."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"text": text, "method": "plaintext"}
    except Exception as exc:
        return {"text": "", "method": "failed", "error": str(exc)}


def _extract_pymupdf(path: Path, doc: "Any | None" = None) -> dict:
    """Extract text from a text-layer PDF via pymupdf.

    Accepts an optional pre-opened doc to avoid re-opening after classification.
    """
    if not _HAS_PYMUPDF:
        return _extract_document_extractor_fallback(path)
    try:
        owned = doc is None
        if owned:
            doc = _open_pdf(path)
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text("text"))
        if owned:
            doc.close()
        return {"text": "\n".join(pages), "method": "pymupdf", "pages": len(pages)}
    except Exception as exc:
        return {"text": "", "method": "failed", "error": str(exc)}


def render_pdf_pages_to_png(path: Path, *, dpi: int = 200, max_pages: int | None = None) -> list[bytes]:
    """Render PDF pages to PNG bytes for vision OCR.

    Returns [] for an unopenable/corrupt PDF (e.g. a Google Drive online-only
    stub) rather than raising — callers treat empty as "could not OCR" and keep
    the original entry.
    """
    if not _HAS_PYMUPDF:
        return []
    try:
        doc = _open_pdf(path)
    except Exception:  # noqa: BLE001 — unreadable/corrupt PDF; skip, never crash the batch
        return []
    matrix = _pymupdf.Matrix(dpi / 72, dpi / 72)  # type: ignore[union-attr]
    images: list[bytes] = []
    try:
        for index, page in enumerate(doc):
            if max_pages is not None and index >= max_pages:
                break
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))
    except Exception:  # noqa: BLE001 — partial render failure; return what we have
        pass
    finally:
        doc.close()
    return images


_VISION_OCR_PROMPT = (
    "Transcribe ALL text visible in this image in natural human reading order. "
    "Preserve the original language and the correct word/letter order (for "
    "right-to-left scripts like Hebrew, output proper logical order). Output only "
    "the transcribed text, no commentary."
)


def extract_text_via_vision_ocr(
    path: Path, *, client: "Any | None" = None, max_pages: int = 20, dpi: int = 200
) -> dict:
    """Re-OCR a PDF with the local vision model (glm-ocr) to recover correct text.

    Renders pages to images and transcribes them, so the result follows the
    visual glyphs in reading order — fixing PDFs whose text layer stores RTL
    text reversed. Returns {text, method, pages}.
    """
    if not _HAS_PYMUPDF:
        return {"text": "", "method": "failed", "error": "pymupdf unavailable"}
    if client is None:
        from src.lib.ai import get_llm_client

        client = get_llm_client("document_ocr")
    images = render_pdf_pages_to_png(path, dpi=dpi, max_pages=max_pages)
    if not images:
        return {"text": "", "method": "failed", "error": "no pages rendered"}
    pages: list[str] = []
    for img in images:
        try:
            text = client.generate_with_vision(
                prompt=_VISION_OCR_PROMPT, images=[img], temperature=0.0, max_tokens=2048
            )
        except Exception:  # noqa: BLE001 — best-effort per page
            text = ""
        if text and text.strip():
            pages.append(text.strip())
    return {
        "text": "\n\n".join(pages),
        "method": "vision-ocr-glm",
        "pages": len(images),
    }


def _check_mlx_vlm() -> bool:
    """Return True if mlx-vlm is importable (cached after first check)."""
    global _HAS_MLX_VLM
    if _HAS_MLX_VLM is not None:
        return _HAS_MLX_VLM
    try:
        import mlx_vlm  # type: ignore[import]  # noqa: F401

        _HAS_MLX_VLM = True
    except ImportError:
        _HAS_MLX_VLM = False
    return _HAS_MLX_VLM


_MLX_MODEL_ID = "mlx-community/Qwen2-VL-2B-Instruct-4bit"
_mlx_model_cache: "tuple | None" = None  # (model, processor)


def _get_mlx_model():
    """Load MLX model once, cache for reuse across calls."""
    global _mlx_model_cache
    if _mlx_model_cache is None:
        from mlx_vlm import load  # type: ignore[import]

        _mlx_model_cache = load(_MLX_MODEL_ID)
    return _mlx_model_cache


def _extract_image_ocr(path: Path) -> dict:
    """Extract text from an image using MLX OCR.

    Falls back to document-extractor if mlx-vlm is not available.
    """
    if not _check_mlx_vlm():
        return _extract_document_extractor_fallback(path)

    try:
        from mlx_vlm import generate  # type: ignore[import]

        model, processor = _get_mlx_model()
        result = generate(
            model,
            processor,
            str(path),
            prompt="Extract all text from this image verbatim.",
            max_tokens=2048,
        )
        text = result if isinstance(result, str) else str(result)
        return {"text": text, "method": "mlx-vlm"}
    except Exception as exc:
        return {"text": "", "method": "failed", "error": str(exc)}


def _extract_document_extractor_fallback(path: Path) -> dict:
    """Delegate to the document-extractor skill's extractor.py.

    Returns an empty-text result if the skill is not available.
    """
    if extract is None:
        return {"text": "", "method": "failed", "error": "document-extractor not available"}
    try:
        result = extract(path)
        # ExtractionResult has .markdown and .success attributes
        text = getattr(result, "markdown", "") or ""
        success = getattr(result, "success", False)
        method = "document-extractor" if success else "failed"
        return {"text": text, "method": method}
    except Exception as exc:
        return {"text": "", "method": "failed", "error": str(exc)}


# ---------------------------------------------------------------------------
# Main extraction entry point
# ---------------------------------------------------------------------------


def extract_text(path: Path) -> dict:
    """Extract text from *path*, routing to the appropriate method.

    Returns a dict with at minimum:
        text   : str   — extracted text (empty string on failure)
        method : str   — which method was used
    May also include:
        pages  : int   — page count (PDF extraction)
        error  : str   — error message on failure
    """
    suffix = path.suffix.lower()

    if suffix in _PLAINTEXT_EXTS:
        return _extract_plaintext(path)
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix in _IMAGE_EXTS:
        return _extract_image_ocr(path)
    if suffix in _OFFICE_EXTS or suffix in _HTML_EXTS:
        return _extract_document_extractor_fallback(path)

    # unknown — attempt plaintext read
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"text": text, "method": "plaintext"}
    except Exception:
        return {"text": "", "method": "failed", "error": f"unknown suffix: {suffix}"}


# ---------------------------------------------------------------------------
# Cached extraction
# ---------------------------------------------------------------------------


def _md5_of_file(path: Path) -> str:
    """Return the MD5 hex digest of *path*'s byte content."""
    try:
        from ._indexer_helpers import _checksum
    except ImportError:
        from _indexer_helpers import _checksum
    return _checksum(path)


def extract_with_cache(path: Path, cache_dir: Path) -> dict:
    """Extract text with checksum-based caching.

    Cache key: MD5 of file bytes.
    Cache file: ``{cache_dir}/{stem}_{checksum}.json``.

    Returns the cached result (with ``cached=True``) if the file's checksum
    matches a previously stored result; otherwise extracts fresh and writes
    the cache entry.
    """
    checksum = _md5_of_file(path)
    cache_file = cache_dir / f"{path.stem}_{checksum}.json"

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            cached["cached"] = True
            return cached
        except Exception:
            pass  # Corrupt cache — re-extract below

    result = extract_text(path)
    result["checksum"] = checksum

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # Cache write failure is non-fatal

    return result
