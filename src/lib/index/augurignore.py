"""File-driven exclusion for the documents indexer (spec 2026-06-13).

Reads `.augurignore` (a gitignore-style subset) at the documents source root and
decides whether a source-relative path must be excluded from indexing AND Browse
listing. Stdlib only; fail-closed (when unsure, ignore — sensitive data must not
leak). Absent file => no-op.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

AUGURIGNORE = ".augurignore"


def load_augurignore(root: Path) -> list[str]:
    """Return the list of patterns from <root>/.augurignore (empty if absent)."""
    path = root / AUGURIGNORE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    patterns: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def path_is_ignored(rel_posix: str, patterns: list[str]) -> bool:
    """True if the source-root-relative POSIX path matches any pattern.

    Supported subset:
      - "dir/"        -> ignore everything under that path prefix
      - "**/glob"     -> glob matched against the basename and any segment
      - "name"/"glob" -> match the full rel path or any single path segment
    """
    if not patterns:
        return False
    # Case-insensitive matching (fnmatch is case-sensitive on POSIX). Sensitive
    # data must not leak on a capitalization mismatch (Recovery vs recovery).
    rel = rel_posix.strip("/").lower()
    segments = rel.split("/")
    for pat in patterns:
        p = pat.strip().lower()
        if not p:
            continue
        if p.endswith("/"):
            prefix = p.rstrip("/")
            if rel == prefix or rel.startswith(prefix + "/"):
                return True
            continue
        if p.startswith("**/"):
            glob = p[3:]
            if any(fnmatch.fnmatchcase(seg, glob) for seg in segments):
                return True
            continue
        if fnmatch.fnmatchcase(rel, p) or any(fnmatch.fnmatchcase(seg, p) for seg in segments):
            return True
    return False
