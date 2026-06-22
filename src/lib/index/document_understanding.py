"""Canonical document understanding router for imported documents.

This module gives the ambient-import/RAG path one stable entry point for
document extraction plus light structured understanding.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_COPYRIGHT_RE = re.compile(r"©|\ball rights reserved\b|\bcopyright\b|\(c\)\s*\d", re.IGNORECASE)

try:
    from src.lib.extraction import extract
except ImportError:  # pragma: no cover — extraction library always available post-Track-1
    extract = None  # type: ignore[assignment]

UNDERSTANDING_VERSION = "v3"


def understand_document(path: Path) -> dict[str, Any]:
    """Extract and lightly understand a document from a single canonical path."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        extracted = _extract_text_pdf(path) or _extract_via_document_extractor(path) or _empty_result(path)
    else:
        extracted = _extract_via_document_extractor(path) or _extract_text_like(path) or _empty_result(path)

    method = str(extracted.get("method") or "unknown")
    ocr_applied = bool(extracted.get("ocr_applied"))
    llm_assisted = bool(extracted.get("llm_assisted"))
    body = str(extracted.get("body") or "").strip()
    title = str(extracted.get("title") or "").strip()
    # The low-level extractor falls back to the filename stem for most formats
    # (it never reads markdown frontmatter or headings). When all we got back is
    # the bare stem, derive a human-readable title from the body instead so
    # Browse cards show "L28 — Pitch Deck Review", not "L28".
    if not title or title == path.stem:
        inferred = _infer_title(body, fallback=path.stem)
        if inferred and inferred != path.stem:
            title = inferred
    if not title:
        title = path.stem
    warnings = _low_signal_warnings(body)

    return {
        "body": body,
        "title": title,
        "format": suffix.lstrip(".") or "unknown",
        "document_kind": "pdf" if suffix == ".pdf" else "document",
        "extraction_method": method,
        "ocr_applied": ocr_applied,
        "summary": _summarize(body=body, title=title),
        "key_insights": _key_insights(body),
        "section_hints": _section_hints(body),
        "action_candidates": _action_candidates(body),
        "extraction_confidence": _extraction_confidence(body, method=method, warnings=warnings),
        "low_signal_warnings": warnings,
        "llm_assisted": llm_assisted,
        "visual_structure_used": ocr_applied,
        "understanding_version": UNDERSTANDING_VERSION,
        "error": extracted.get("error"),
    }


def _extract_text_pdf(path: Path) -> dict[str, Any] | None:
    try:
        from .ocr_extractor import extract_text
    except ImportError:
        from ocr_extractor import extract_text

    result = extract_text(path)
    text = str(result.get("text") or "").strip()
    if not text:
        return None
    return {
        "body": text,
        "title": _infer_title(text, fallback=path.stem),
        "method": result.get("method", "unknown"),
        "ocr_applied": result.get("method") not in {"pymupdf", "plaintext"},
    }


def _extract_via_document_extractor(path: Path) -> dict[str, Any] | None:
    if extract is None:
        return None

    try:
        result = extract(str(path), max_tier=1)
    except Exception:
        return None

    if not result.success:
        return None
    return {
        "body": result.markdown,
        "title": result.title or path.stem,
        "method": f"document-extractor:{result.tier_used}",
        "ocr_applied": result.ocr_applied,
        "llm_assisted": result.tier_used == 1 or bool(getattr(result, "needs_llm", False)),
    }


def _extract_text_like(path: Path) -> dict[str, Any] | None:
    if path.suffix.lower() not in {
        ".csv",
        ".htm",
        ".html",
        ".json",
        ".markdown",
        ".md",
        ".rst",
        ".svg",
        ".tex",
        ".text",
        ".toml",
        ".tsv",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }:
        return None
    try:
        body = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        body = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if not body.strip():
        return None
    return {
        "body": body,
        "title": _infer_title(body, fallback=path.stem),
        "method": "text-like",
        "ocr_applied": False,
        "llm_assisted": False,
    }


def _empty_result(path: Path) -> dict[str, Any]:
    return {
        "body": "",
        "title": path.stem,
        "method": "failed",
        "ocr_applied": False,
        "error": "No extractor result",
    }


# A genuine document title (H1) sits at the very top. Bound the heading scan to
# the first N non-empty lines so a "#"-prefixed code/shell comment deep in the
# body of a plaintext/pymupdf-extracted document can never be picked as a title.
_TITLE_HEADING_WINDOW = 15


def _infer_title(text: str, fallback: str) -> str:
    # 1. YAML frontmatter `title:` wins when present.
    fm_title = _frontmatter_title(text)
    if fm_title:
        return fm_title[:140]
    body = _strip_frontmatter(text)
    # 2. First markdown heading (# ...), but only in the title region near the
    # top. Plaintext/pymupdf extraction has no markdown structure, so a "#" line
    # deep in the body is a code/shell comment (e.g. "# One-time setup" inside a
    # snippet), not an H1 — a real title lives at the top of the document.
    nonempty_seen = 0
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        nonempty_seen += 1
        if nonempty_seen > _TITLE_HEADING_WINDOW:
            break
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if len(heading) >= 3 and not is_noise_title(heading):
                return heading[:140]
    # 3. First meaningful non-frontmatter, non-markup line.
    for line in body.splitlines():
        stripped = line.strip()
        if len(stripped) >= 8 and not _looks_like_frontmatter_kv(stripped) and not is_noise_title(stripped):
            return stripped[:140]
    return fallback


def is_noise_title(text: str) -> bool:
    """True for lines that are markup/boilerplate, never a real document title.

    Catches MarkItDown artifacts (HTML comments like ``<!-- Slide number: 1 -->``),
    raw HTML tags, markdown images, and horizontal rules.
    """
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith(("<!--", "<", "![", "---", "===", "***", "___", "|")):
        return True
    # A line that is only an image/link or table pipe noise.
    if set(stripped) <= set("-=*_| \t"):
        return True
    # Legal/copyright boilerplate is never a document title.
    if _COPYRIGHT_RE.search(stripped):
        return True
    compact = stripped.replace(" ", "")
    letters = sum(ch.isalpha() for ch in stripped)
    # Mostly digits/punctuation/codes ("(*294589)", page numbers, dates).
    if letters < 3 or letters < 0.45 * max(1, len(compact)):
        return True
    # Latin-1 mojibake (mis-decoded Hebrew/UTF-8 shows as accented-char clusters).
    latin1_accents = sum(1 for ch in stripped if 0xC0 <= ord(ch) <= 0xFF)
    if latin1_accents >= 4 and latin1_accents > 0.3 * letters:
        return True
    return False


def _strip_frontmatter(text: str) -> str:
    """Return the body with a leading ``---`` YAML frontmatter block removed."""
    if not text.startswith("---"):
        return text
    lines = text.splitlines()
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :])
    return text


def _frontmatter_title(text: str) -> str:
    """Extract the ``title:`` value from a leading YAML frontmatter block."""
    if not text.startswith("---"):
        return ""
    lines = text.splitlines()
    for index in range(1, len(lines)):
        line = lines[index]
        if line.strip() == "---":
            break
        if line.startswith("title:"):
            value = line.split(":", 1)[1].strip()
            return value.strip("'\"").strip()
    return ""


def _looks_like_frontmatter_kv(line: str) -> bool:
    """True for ``key: value`` lines that are frontmatter noise, not a title."""
    if ":" not in line:
        return False
    key = line.split(":", 1)[0].strip()
    return bool(key) and " " not in key and key.replace("_", "").replace("-", "").isalnum()


def _summarize(*, body: str, title: str) -> str:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return f"{title} was imported, but no readable text was captured."
    summary = " ".join(lines[:3])
    return summary[:320]


def _key_insights(body: str) -> list[str]:
    insights: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if len(stripped) >= 30 and stripped not in insights:
            insights.append(stripped)
        if len(insights) == 5:
            break
    return insights


def _section_hints(body: str) -> list[str]:
    hints: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and stripped == stripped.title() and len(stripped.split()) <= 6:
            hints.append(stripped)
        if len(hints) == 8:
            break
    return hints


def _extraction_confidence(body: str, *, method: str, warnings: list[str]) -> str:
    if warnings or method == "failed":
        return "low"
    if method in {"unknown", "failed"} or len(body.split()) < 80:
        return "medium"
    return "high"


def _action_candidates(body: str) -> list[str]:
    candidates: list[str] = []
    action_prefixes = (
        "apply",
        "approve",
        "book",
        "call",
        "complete",
        "email",
        "file",
        "follow up",
        "pay",
        "prepare",
        "review",
        "schedule",
        "send",
        "submit",
        "upload",
    )
    for line in body.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped and lowered.startswith(action_prefixes) and stripped not in candidates:
            candidates.append(stripped)
        if len(candidates) == 5:
            break
    return candidates


def _low_signal_warnings(body: str) -> list[str]:
    stripped = body.strip()
    if not stripped:
        return ["empty_body"]
    if len(stripped.split()) < 4:
        return ["short_body"]
    if _symbol_ratio(stripped) > 0.35:
        return ["high_symbol_ratio"]
    return []


def _symbol_ratio(text: str) -> float:
    if not text:
        return 0.0
    symbols = sum(1 for char in text if not char.isalnum() and not char.isspace())
    return symbols / len(text)
