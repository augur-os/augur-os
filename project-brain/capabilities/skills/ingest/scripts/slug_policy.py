"""Capture-name policy (naming spec 2026-06-12): short, date-free slugs.

Dates live in frontmatter; event-dated writers (meetings, audio) keep their
own date prefixes and do NOT use capture_slug.
"""
from __future__ import annotations

import re
from pathlib import Path

_MAX_WORDS = 6
_MAX_LEN = 40
_URL_NOISE = re.compile(r"^(https?|www)$")
# Unicode-aware word split (spec Hebrew policy: meaningful Hebrew names beat
# transliteration — non-ASCII word characters are kept, not dropped).
_WORD_SPLIT = re.compile(r"[^\w]+", re.UNICODE)


def capture_slug(title: str) -> str:
    """Return a short, date-free, filesystem-safe slug for a capture note.

    Splits *title* (or URL) on non-word characters (unicode-aware, so Hebrew
    and other scripts survive), drops URL-scheme noise tokens (http/https/www)
    and pure-underscore tokens, lowercases (no-op for unicased scripts), takes
    the first _MAX_WORDS tokens, and caps at _MAX_LEN characters (character
    count, not bytes — Python str slicing is per-character). Returns
    "untitled" only when zero word tokens remain (emoji-only or
    punctuation-only input).
    """
    words = [
        w
        for w in _WORD_SPLIT.split(title.lower())
        if w and w.strip("_") and not _URL_NOISE.match(w)
    ]
    slug = "-".join(words[:_MAX_WORDS])
    return slug[:_MAX_LEN].rstrip("-") or "untitled"


def unique_name(directory: Path, stem: str) -> str:
    """Return *stem* if ``<directory>/<stem>.md`` is free, else ``<stem>-2``, etc."""
    if not (directory / f"{stem}.md").exists():
        return stem
    n = 2
    while (directory / f"{stem}-{n}.md").exists():
        n += 1
    return f"{stem}-{n}"


__all__ = ["capture_slug", "unique_name"]
