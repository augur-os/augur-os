"""Detect documents whose Hebrew text was extracted in reversed (visual) order.

Some PDFs store Hebrew glyphs in visual left-to-right order, so text extractors
(PyMuPDF, MarkItDown) return each word's letters reversed — "סניף" becomes
"ףינס". The unambiguous signal is a *final-form* Hebrew letter (ך ם ן ף ץ)
appearing anywhere but the end of its word: in correct Hebrew those forms occur
only word-finally, so a leading/medial final-form means the word is reversed.

Detection is intentionally conservative — correct Hebrew yields a ratio of 0.0,
so callers never re-OCR or rewrite text that is already right.
"""

from __future__ import annotations

# Final-form Hebrew letters: legal only as the last letter of a word.
_FINAL_FORMS = set("ךםןףץ")
_HEBREW_RANGE = ("א", "ת")  # alef..tav (base letters)
_STRIP = ".,:;()[]{}\"'!?־ |/\\-–—"

# Correct Hebrew scores 0.0; incidental OCR glitches stay <= ~0.10; genuinely
# reversed documents (e.g. number-heavy invoices with a reversed title) land at
# 0.15+. 0.15 separates them without flagging clean text.
REVERSAL_THRESHOLD = 0.15


def _has_hebrew(token: str) -> bool:
    return any(_HEBREW_RANGE[0] <= ch <= _HEBREW_RANGE[1] or ch in _FINAL_FORMS for ch in token)


def _token_is_reversed(token: str) -> bool:
    core = token.strip(_STRIP)
    if len(core) < 2:
        return False
    # A final-form letter at any position except the last => reversed word.
    return any(core[i] in _FINAL_FORMS for i in range(len(core) - 1))


def hebrew_reversal_ratio(text: str) -> float:
    """Fraction of Hebrew tokens that carry the reversal signal (0.0 if none).

    Returns 0.0 when there are no Hebrew tokens, so non-Hebrew and clean Hebrew
    are both treated as not-reversed.
    """
    hebrew_tokens = 0
    reversed_tokens = 0
    for token in text.split():
        if not _has_hebrew(token):
            continue
        hebrew_tokens += 1
        if _token_is_reversed(token):
            reversed_tokens += 1
    if hebrew_tokens == 0:
        return 0.0
    return reversed_tokens / hebrew_tokens


def is_reversed_document(text: str, *, threshold: float = REVERSAL_THRESHOLD) -> bool:
    """True only when reversed Hebrew is strong and consistent enough to act on."""
    return hebrew_reversal_ratio(text) >= threshold


def reocr_reversed_documents(rag_dir, *, limit=None, max_pages: int = 20, client=None) -> dict[str, int]:
    """Re-OCR document entries whose stored body is reversed Hebrew.

    For each affected entry whose source is a readable PDF, re-extract via the
    local vision OCR (glm-ocr). The new text replaces the body and re-derives
    the title ONLY when it is non-empty AND no longer reversed — otherwise the
    original entry is kept untouched (never write worse content).
    """
    from pathlib import Path

    from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter
    from src.lib.index.document_understanding import _infer_title, is_noise_title
    from src.lib.index.ocr_extractor import extract_text_via_vision_ocr

    documents_root = Path(rag_dir) / "documents"
    scanned = repaired = skipped = failed = 0
    if not documents_root.is_dir():
        return {"scanned": 0, "repaired": 0, "skipped": 0, "failed": 0}

    for entry in sorted(documents_root.rglob("*.md")):
        if entry.name == "index.md":
            continue
        meta, body = parse_frontmatter(entry)
        if meta.get("type") != "document":
            continue
        if not is_reversed_document(body):
            continue
        scanned += 1
        source = str(meta.get("source_path") or "")
        src_path = Path(source)
        if not source.lower().endswith(".pdf") or not src_path.is_file():
            skipped += 1
            continue
        result = extract_text_via_vision_ocr(src_path, client=client, max_pages=max_pages)
        new_text = str(result.get("text") or "").strip()
        if not new_text or is_reversed_document(new_text):
            failed += 1
            continue
        meta["document_extraction_method"] = result.get("method", "vision-ocr-glm")
        stem = str(meta.get("name") or entry.stem)
        new_title = _infer_title(new_text, fallback=stem)
        if new_title and new_title != stem and not is_noise_title(new_title):
            meta["title"] = new_title
            meta["document_title"] = new_title
            meta.pop("title_source", None)
        write_frontmatter(entry, meta, new_text)
        repaired += 1
        if limit is not None and repaired >= limit:
            break

    return {"scanned": scanned, "repaired": repaired, "skipped": skipped, "failed": failed}
