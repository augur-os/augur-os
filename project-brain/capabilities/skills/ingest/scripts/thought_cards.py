"""Pure-logic helpers for freeform thought notes."""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from src.lib.brain_layout import brain_capture_dir
from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter
from skills.ingest.scripts.slug_policy import capture_slug, unique_name

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def slugify_thought(text: str, max_len: int = 64) -> str:
    """Return a filesystem-safe slug for a thought note."""
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    slug = _SLUG_STRIP_RE.sub("-", first_line.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "thought"


def compute_thought_hash(body: str) -> str:
    """Content hash of the freeform thought body."""
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


def _unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    for index in range(2, 10_000):
        candidate = target.with_name(f"{target.stem}-{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find available thought note path for {target}")


def write_thought_card(
    *,
    vault_dir: Path,
    body: str,
    title: str = "",
    captured_at: datetime | None = None,
) -> Path:
    """Persist a freeform thought under <vault_dir>/notes/ and return its path."""
    if not body.strip():
        raise ValueError("body is required")

    captured_at = captured_at or datetime.now(UTC)
    notes_dir = brain_capture_dir(vault_dir)
    notes_dir.mkdir(parents=True, exist_ok=True)
    resolved_title = title.strip() or body.strip().splitlines()[0][:80].strip()
    # Naming spec 2026-06-12 Wave 3: date-free slug from title (or body first
    # line); date lives in frontmatter captured_at.
    target = notes_dir / f"{unique_name(notes_dir, capture_slug(resolved_title or body))}.md"

    frontmatter = {
        "title": resolved_title or "Thought",
        "source_type": "thought",
        "x-augur-note-type": "thought",
        "content_hash": compute_thought_hash(body),
        "captured_at": captured_at.isoformat().replace("+00:00", "Z"),
        "tags": ["thought"],
    }
    write_vault_frontmatter(target, frontmatter, body.rstrip() + "\n")
    return target


def find_existing_thought_card(vault_dir: Path, content_hash: str) -> Path | None:
    """Return the thought note whose content_hash matches, else None."""
    notes_dir = brain_capture_dir(vault_dir)
    if not notes_dir.is_dir():
        return None
    for path in sorted(notes_dir.glob("*.md")):
        try:
            meta, _ = parse_frontmatter(path)
        except Exception:
            continue
        if meta.get("content_hash") == content_hash:
            return path
    return None


__all__ = [
    "compute_thought_hash",
    "find_existing_thought_card",
    "slugify_thought",
    "write_thought_card",
]
