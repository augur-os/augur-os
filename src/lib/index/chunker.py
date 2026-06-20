"""Content-aware chunking strategies for RAG indexing.

Each returned chunk is a dict with:
  text           — the chunk text
  chunk_index    — 0-based position within this document
  total_chunks   — total number of chunks for the document
  section_heading — heading of the section this chunk belongs to (str, may be "")
  parent_heading  — heading of the parent section (str, may be "")
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Internal types / helpers
# ---------------------------------------------------------------------------

Chunk = dict[str, Any]

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)


def _make_chunk(
    text: str,
    chunk_index: int,
    total_chunks: int,
    section_heading: str = "",
    parent_heading: str = "",
) -> Chunk:
    return {
        "text": text,
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "section_heading": section_heading,
        "parent_heading": parent_heading,
    }


def _finalize(chunks: list[Chunk]) -> list[Chunk]:
    """Back-fill total_chunks once we know the final count."""
    total = len(chunks)
    for i, chunk in enumerate(chunks):
        chunk["chunk_index"] = i
        chunk["total_chunks"] = total
    return chunks


def _sliding_window(
    text: str,
    chunk_size: int,
    overlap: int,
    section_heading: str = "",
    parent_heading: str = "",
) -> list[Chunk]:
    """Generic sliding-window splitter that tries to break at sentence boundaries."""
    chunks: list[Chunk] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)

        if end < n:
            # Try to find a sentence boundary (". " or "\n") within the last
            # `overlap` characters of the window so we don't cut mid-sentence.
            search_from = max(start, end - overlap)
            nl_pos = text.rfind("\n", search_from, end)
            dot_pos = text.rfind(". ", search_from, end)
            boundary = max(nl_pos, dot_pos)
            if boundary > start:
                end = boundary + 1  # include the boundary character

        window = text[start:end]
        chunks.append(
            _make_chunk(
                text=window,
                chunk_index=0,  # placeholder; finalized later
                total_chunks=0,
                section_heading=section_heading,
                parent_heading=parent_heading,
            )
        )

        # Advance by (chunk_size - overlap), but at least 1 to avoid infinite loop
        advance = max(chunk_size - overlap, 1)
        start = start + advance
        if start >= n:
            break

    return chunks


# ---------------------------------------------------------------------------
# chunk_markdown
# ---------------------------------------------------------------------------


def chunk_markdown(
    text: str,
    chunk_size: int = 1500,
    overlap: int = 200,
) -> list[Chunk]:
    """Heading-aware sliding window chunker for Markdown files.

    Parses the document into sections by heading level (#, ##, ###, …).
    Each section that fits within `chunk_size` is kept as a single chunk.
    Sections exceeding `chunk_size` are split with a sliding window that
    prefers sentence boundaries.
    """
    if not text:
        return []

    # Split text into sections at heading boundaries.
    # We preserve heading lines as section headers.
    sections: list[tuple[str, str, str]] = []  # (heading_text, parent_heading, body)
    heading_stack: list[tuple[int, str]] = []  # (level, heading_text)

    lines = text.split("\n")
    current_heading = ""
    current_parent = ""
    current_body_lines: list[str] = []

    def _flush():
        body = "\n".join(current_body_lines).strip()
        if body or current_heading:
            sections.append((current_heading, current_parent, body))

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            _flush()
            current_body_lines = []

            level = len(m.group(1))
            heading = m.group(2).strip()

            # Pop the stack down to the parent level
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()

            current_parent = heading_stack[-1][1] if heading_stack else ""
            current_heading = heading
            heading_stack.append((level, heading))
        else:
            current_body_lines.append(line)

    _flush()

    # Build chunks from sections
    raw_chunks: list[Chunk] = []
    for sec_heading, par_heading, body in sections:
        if not body:
            continue  # Skip headings with no body — they inflate the index

        if len(body) <= chunk_size:
            raw_chunks.append(
                _make_chunk(
                    text=body,
                    chunk_index=0,
                    total_chunks=0,
                    section_heading=sec_heading,
                    parent_heading=par_heading,
                )
            )
        else:
            # Sliding window within the section
            raw_chunks.extend(_sliding_window(body, chunk_size, overlap, sec_heading, par_heading))

    return _finalize(raw_chunks)


# ---------------------------------------------------------------------------
# chunk_code
# ---------------------------------------------------------------------------

# Boundary patterns for Python and TypeScript/JavaScript
_PY_BOUNDARY_RE = re.compile(r"^(?:async\s+def|def|class)\s+(\w+)", re.MULTILINE)
_TS_BOUNDARY_RE = re.compile(
    r"^(?:export\s+(?:default\s+)?(?:async\s+)?function|export\s+class|"
    r"(?:export\s+)?const\s+\w+\s*=\s*(?:async\s+)?\()",
    re.MULTILINE,
)


def _split_at_boundaries(text: str, boundary_re: re.Pattern) -> list[tuple[str, str]]:
    """Split `text` at regex boundary matches. Returns list of (name, block) tuples."""
    matches = list(boundary_re.finditer(text))
    if not matches:
        return [("", text)]

    blocks: list[tuple[str, str]] = []

    # Any preamble before the first boundary
    preamble = text[: matches[0].start()].strip()
    if preamble:
        blocks.append(("", preamble))

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        # Extract the name — group 1 if present, else first word after keyword
        name = m.group(1) if m.lastindex and m.group(1) else m.group(0).split()[0]
        blocks.append((name, block))

    return blocks


def chunk_code(
    text: str,
    chunk_size: int = 2000,
    overlap: int = 100,
) -> list[Chunk]:
    """Function/class boundary-aware chunker for Python and TypeScript files.

    Splits at `def`, `class`, `async def`, `export function`, etc.
    If a single block exceeds `chunk_size`, applies a sliding window fallback.
    """
    if not text:
        return []

    # Determine language heuristically
    if _PY_BOUNDARY_RE.search(text):
        blocks = _split_at_boundaries(text, _PY_BOUNDARY_RE)
    elif _TS_BOUNDARY_RE.search(text):
        blocks = _split_at_boundaries(text, _TS_BOUNDARY_RE)
    else:
        # No recognised boundaries — fall back to sliding window
        blocks = [("", text)]

    raw_chunks: list[Chunk] = []
    for name, block in blocks:
        if not block:
            continue
        if len(block) <= chunk_size:
            raw_chunks.append(
                _make_chunk(
                    text=block,
                    chunk_index=0,
                    total_chunks=0,
                    section_heading=name,
                    parent_heading="",
                )
            )
        else:
            raw_chunks.extend(_sliding_window(block, chunk_size, overlap, name, ""))

    return _finalize(raw_chunks)


# ---------------------------------------------------------------------------
# chunk_paragraphs
# ---------------------------------------------------------------------------


def chunk_paragraphs(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[Chunk]:
    """Paragraph-based sliding window chunker for general documents.

    Splits on double newlines, accumulates paragraphs until `chunk_size` is
    reached, then emits a chunk. The next chunk is prepended with the last
    `overlap` characters of the previous chunk.
    """
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return [_make_chunk(text=text.strip(), chunk_index=0, total_chunks=1)]

    raw_chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_len = 0
    overlap_prefix = ""

    def _emit():
        nonlocal overlap_prefix
        body = overlap_prefix + "\n\n".join(current_parts)
        raw_chunks.append(_make_chunk(text=body, chunk_index=0, total_chunks=0))
        # Compute overlap for next chunk
        overlap_prefix = body[-overlap:] if overlap and len(body) > overlap else ""
        if overlap_prefix:
            overlap_prefix += "\n\n"

    for para in paragraphs:
        para_len = len(para)
        # +2 for the "\n\n" separator we'd add between paragraphs
        projected = current_len + (2 if current_parts else 0) + para_len

        if projected > chunk_size and current_parts:
            _emit()
            current_parts = []
            current_len = 0

        current_parts.append(para)
        current_len += (2 if len(current_parts) > 1 else 0) + para_len

    if current_parts:
        _emit()

    return _finalize(raw_chunks)


# ---------------------------------------------------------------------------
# auto_chunk — dispatcher
# ---------------------------------------------------------------------------

_CODE_CONTENT_TYPES = {"python", "py", "typescript", "ts", "javascript", "js"}
_MARKDOWN_CONTENT_TYPES = {"markdown", "md"}


def auto_chunk(
    text: str,
    content_type: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
    small_file_threshold: int = 500,
) -> list[Chunk]:
    """Dispatcher that routes to the appropriate chunking strategy.

    If `text` is shorter than `small_file_threshold`, returns a single chunk
    regardless of content type.  Otherwise routes by `content_type`.
    """
    if len(text) < small_file_threshold:
        return _finalize([_make_chunk(text=text, chunk_index=0, total_chunks=1)])

    ct = content_type.lower().lstrip(".")

    if ct in _MARKDOWN_CONTENT_TYPES:
        kwargs: dict[str, Any] = {}
        if chunk_size is not None:
            kwargs["chunk_size"] = chunk_size
        if overlap is not None:
            kwargs["overlap"] = overlap
        return chunk_markdown(text, **kwargs)

    if ct in _CODE_CONTENT_TYPES:
        kwargs = {}
        if chunk_size is not None:
            kwargs["chunk_size"] = chunk_size
        if overlap is not None:
            kwargs["overlap"] = overlap
        return chunk_code(text, **kwargs)

    # Default: paragraph-based
    kwargs = {}
    if chunk_size is not None:
        kwargs["chunk_size"] = chunk_size
    if overlap is not None:
        kwargs["overlap"] = overlap
    return chunk_paragraphs(text, **kwargs)
