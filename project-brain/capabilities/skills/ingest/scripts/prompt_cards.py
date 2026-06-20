"""Pure-logic helpers for user-saved prompt cards (ADR-748).

Mirrors url_ingest.py but targets <vault>/notes/ and adds {{placeholder}}
extraction. No MCP, no I/O beyond the explicit vault_dir argument.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

from src.lib.brain_layout import brain_capture_dir
from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter
from skills.ingest.scripts.slug_policy import capture_slug, unique_name

_PLACEHOLDER_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def slugify_label(label: str, max_len: int = 80) -> str:
    """Filesystem-safe slug from a human label."""
    slug = _SLUG_STRIP_RE.sub("-", label.strip().lower()).strip("-")
    return slug[:max_len].rstrip("-") or "prompt"


def extract_placeholders(body: str) -> list[str]:
    """Return {{slot}} names in first-seen order, deduplicated."""
    seen: list[str] = []
    for name in _PLACEHOLDER_RE.findall(body):
        if name not in seen:
            seen.append(name)
    return seen


def compute_prompt_hash(body: str) -> str:
    """Content hash of the prompt body, used for dedupe."""
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


def _unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    for index in range(2, 10_000):
        candidate = target.with_name(f"{target.stem}-{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find available prompt card path for {target}")


def write_prompt_card(
    *,
    vault_dir: Path,
    label: str,
    description: str,
    body: str,
    source_url: str = "",
    icon: str = "MessageSquare",
    today: date | None = None,
) -> Path:
    """Persist a prompt card under the vault capture dir and return its path."""
    today = today or date.today()  # kept for backward-compat; date lives in frontmatter
    prompts_dir = brain_capture_dir(vault_dir)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify_label(label)
    # Naming spec 2026-06-12 Wave 3: date-free slug from label.
    target = prompts_dir / f"{unique_name(prompts_dir, capture_slug(label))}.md"

    frontmatter = {
        "id": slug,
        "label": label.strip(),
        "description": description.strip(),
        "icon": icon,
        "source": "vault",
        "x-augur-note-type": "prompt",
        "x-augur-prompt-triggerable": True,
        "content_hash": compute_prompt_hash(body),
        "placeholders": extract_placeholders(body),
        "captured_at": today.isoformat(),
    }
    if source_url:
        frontmatter["source_url"] = source_url

    write_vault_frontmatter(target, frontmatter, body.rstrip() + "\n")
    return target


def find_existing_prompt_card(vault_dir: Path, content_hash: str) -> Path | None:
    """Return the prompt card whose content_hash matches, else None."""
    prompts_dir = brain_capture_dir(vault_dir)
    if not prompts_dir.is_dir():
        return None
    for path in sorted(prompts_dir.glob("*.md")):
        try:
            meta, _ = parse_frontmatter(path)
        except Exception:
            continue
        if meta.get("content_hash") == content_hash:
            return path
    return None


__all__ = [
    "compute_prompt_hash",
    "extract_placeholders",
    "find_existing_prompt_card",
    "slugify_label",
    "write_prompt_card",
]
