"""Detect dangling [[wiki-links]] after a relocation."""

from __future__ import annotations

import re
from pathlib import Path

_LINK_RE = re.compile(r"\[\[([^\]|#]+)")


def _slug(target: str) -> str:
    return target.strip().split("/")[-1]


def find_dangling_links(wiki_root: Path) -> list[tuple[str, str]]:
    """Return (source_filename, link_target) for links with no matching page on disk."""
    pages = {p.stem for p in wiki_root.rglob("*.md")}
    dangling: list[tuple[str, str]] = []
    for md in sorted(wiki_root.rglob("*.md")):
        text = md.read_text(encoding="utf-8", errors="ignore")
        for m in _LINK_RE.finditer(text):
            target = m.group(1)
            if _slug(target) not in pages:
                dangling.append((md.name, target))
    return dangling
