"""LLM-assisted titles for documents whose heuristic title is still weak.

Heuristic titling (frontmatter / H1 / first clean line, in
``document_understanding``) leaves many PDFs/spreadsheets showing their bare
filename stem. This module generates a concise human-readable title from the
document body using the vendor-neutral LLM abstraction
(:func:`src.lib.ai.get_llm_client`) — never a hardcoded model — and writes it
into the RAG entry's ``title``/``document_title`` so Browse cards read well.

It is a batch maintenance op (agent/MCP/CLI invoked), never called inline from
the daemon indexer, to keep LLM cost out of the hot path. Reversed-Hebrew
documents are skipped — :mod:`src.lib.index.rtl_repair` detects them and the
re-OCR pass must fix the text before a title can be trusted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.index.document_understanding import is_noise_title
from src.lib.index.rtl_repair import is_reversed_document

MIN_BODY_CHARS = 40
MAX_BODY_CHARS = 6000  # token-safe window sent to the model
MAX_TITLE_CHARS = 140
TITLE_TASK = "document_title"

_REFUSAL_MARKERS = (
    "i cannot",
    "i can't",
    "i'm unable",
    "i am unable",
    "cannot help",
    "as an ai",
    "i'm sorry",
    "no readable",
    "unable to",
)


def needs_llm_title(meta: dict[str, Any], body: str) -> bool:
    """True when an entry would benefit from an LLM-generated title."""
    if str(meta.get("title_source") or "") == "llm":
        return False
    body = body or ""
    if len(body.strip()) < MIN_BODY_CHARS:
        return False
    if is_reversed_document(body):
        return False
    name = str(meta.get("name") or "").strip()
    title = str(meta.get("title") or "").strip()
    if not title:
        return True
    if title == name:
        return True
    if is_noise_title(title):
        return True
    return False


def build_title_prompt(body: str, stem: str) -> tuple[str, str]:
    """Return (system, prompt) asking for a concise human title."""
    system = (
        "You write short, descriptive document titles. Reply with ONLY the title "
        "text — no quotes, no markdown, no preamble, no file name. Keep it under "
        "eight words. Write the title in the same language as the document."
    )
    snippet = body.strip()[:MAX_BODY_CHARS]
    prompt = (
        "Give a concise, human-readable title for the document below. "
        f"Do not reuse the file name \"{stem}\".\n\n"
        f"---\n{snippet}\n---\n\nTitle:"
    )
    return system, prompt


MAX_TITLE_WORDS = 12


def _sanitize_title(raw: str) -> str:
    title = (raw or "").strip()
    # Take the first non-empty line; models sometimes add a trailing explanation.
    for line in title.splitlines():
        if line.strip():
            title = line.strip()
            break
    # Strip a leading "Title:" label and wrapping quotes/backticks.
    for prefix in ("Title:", "title:", "TITLE:"):
        if title.startswith(prefix):
            title = title[len(prefix) :].strip()
    title = title.strip("\"'`*").strip()
    # Keyword/pillar dumps ("A | B | C ...") — keep only the first segment.
    if " | " in title:
        title = title.split(" | ", 1)[0].strip()
    # Cap runaway length (small models ignore "under N words").
    words = title.split()
    if len(words) > MAX_TITLE_WORDS:
        title = " ".join(words[:MAX_TITLE_WORDS])
    return title[:MAX_TITLE_CHARS].strip()


def _is_valid_title(title: str, stem: str) -> bool:
    if not title or title == stem:
        return False
    if is_noise_title(title):
        return False
    # Questions / clarification prompts are not titles (any language).
    if title.rstrip().endswith(("?", "？")):
        return False
    if any(marker in title.lower() for marker in _REFUSAL_MARKERS):
        return False
    return True


def generate_title(body: str, stem: str, *, client: Any = None) -> str | None:
    """Generate a title for ``body`` via the LLM, or None if unusable."""
    if client is None:
        from src.lib.ai import get_llm_client

        client = get_llm_client(TITLE_TASK)
    system, prompt = build_title_prompt(body, stem)
    try:
        raw = client.generate_text(prompt=prompt, system=system, temperature=0.2, max_tokens=40)
    except Exception:  # noqa: BLE001 — titling is best-effort, never fatal
        return None
    title = _sanitize_title(raw)
    return title if _is_valid_title(title, stem) else None


def _write_entry(path: Path, meta: dict[str, Any], body: str) -> None:
    from src.lib.frontmatter_utils import write_frontmatter

    write_frontmatter(path, meta, body)


def backfill_llm_titles(rag_dir: Path, *, limit: int | None = None, client: Any = None) -> dict[str, int]:
    """Generate LLM titles for document entries under ``rag_dir`` that need one.

    Returns counts: scanned, titled, skipped, failed.
    """
    documents_root = Path(rag_dir) / "documents"
    scanned = titled = skipped = failed = 0
    if not documents_root.is_dir():
        return {"scanned": 0, "titled": 0, "skipped": 0, "failed": 0}

    if client is None:
        from src.lib.ai import get_llm_client

        client = get_llm_client(TITLE_TASK)

    for entry in sorted(documents_root.rglob("*.md")):
        if entry.name == "index.md":
            continue
        meta, body = parse_frontmatter(entry)
        if meta.get("type") != "document":
            continue
        scanned += 1
        if not needs_llm_title(meta, body):
            skipped += 1
            continue
        stem = str(meta.get("name") or entry.stem)
        title = generate_title(body, stem, client=client)
        if not title:
            failed += 1
            continue
        meta["title"] = title
        meta["document_title"] = title
        meta["title_source"] = "llm"
        _write_entry(entry, meta, body)
        titled += 1
        if limit is not None and titled >= limit:
            break

    return {"scanned": scanned, "titled": titled, "skipped": skipped, "failed": failed}


def revalidate_llm_titles(rag_dir: Path, *, client: Any = None) -> dict[str, int]:
    """Re-check existing LLM titles against the stricter rules; fix bad ones.

    Truncates keyword dumps, and for invalid titles (questions/refusals) tries a
    fresh generation, then falls back to the heuristic title, else reverts to the
    filename stem. Idempotent.
    """
    from src.lib.index.document_understanding import _infer_title

    documents_root = Path(rag_dir) / "documents"
    checked = fixed = reverted = 0
    if not documents_root.is_dir():
        return {"checked": 0, "fixed": 0, "reverted": 0}

    for entry in sorted(documents_root.rglob("*.md")):
        if entry.name == "index.md":
            continue
        meta, body = parse_frontmatter(entry)
        if meta.get("title_source") != "llm":
            continue
        checked += 1
        stem = str(meta.get("name") or entry.stem)
        current = str(meta.get("title") or "")
        sanitized = _sanitize_title(current)
        if _is_valid_title(sanitized, stem):
            if sanitized != current:
                meta["title"] = sanitized
                meta["document_title"] = sanitized
                _write_entry(entry, meta, body)
                fixed += 1
            continue
        # Invalid (question / refusal / empty): regenerate, else heuristic, else stem.
        new = generate_title(body, stem, client=client)
        if not new:
            heuristic = _infer_title(body, fallback=stem)
            new = heuristic if (heuristic and heuristic != stem and not is_noise_title(heuristic)) else None
            if new:
                meta.pop("title_source", None)
        if new:
            meta["title"] = new
            meta["document_title"] = new
            fixed += 1
        else:
            meta.pop("title", None)
            meta.pop("title_source", None)
            meta["document_title"] = stem
            reverted += 1
        _write_entry(entry, meta, body)

    return {"checked": checked, "fixed": fixed, "reverted": reverted}
