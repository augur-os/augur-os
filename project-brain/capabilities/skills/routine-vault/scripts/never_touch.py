"""Shared never-touch path classifier used by hygiene_scan and hygiene_apply.

The never-touch list is a hard refusal layer: any path matching is
silently skipped at scan time and refused at apply time with category
`never_touch`. The list is intentionally NOT user-configurable in MVP —
these are paths whose movement would break tooling, git, Python, Node,
or Augur itself.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path


# Directory names. Match if any path component (including final basename) is in this set.
NEVER_TOUCH_DIR_NAMES: frozenset[str] = frozenset({
    ".git",
    ".obsidian",
    ".pytest_cache",
    ".tmp.driveupload",
    "node_modules",
    ".venv",
    "__pycache__",
    ".archive",
})

# File-basename globs. Match if the path's final component matches any of these.
NEVER_TOUCH_FILE_GLOBS: frozenset[str] = frozenset({
    "package-lock.json",
    "pnpm-lock.yaml",
    "uv.lock",
    "yarn.lock",
    "*.lock",
})

# Basename prefixes. Match if the path's final component starts with any of these
# AND the component starts with a dot (to avoid colliding with user filenames).
NEVER_TOUCH_PREFIXES: frozenset[str] = frozenset({
    ".augur-",
})


def is_never_touch(path: Path) -> bool:
    """Return True if `path` matches any never-touch rule.

    `path` may be absolute or relative; only the basename and path
    components are inspected.
    """
    parts = path.parts
    # Directory-name match anywhere in the path
    for part in parts:
        if part in NEVER_TOUCH_DIR_NAMES:
            return True
    # Basename glob match
    basename = path.name
    for glob in NEVER_TOUCH_FILE_GLOBS:
        if fnmatch.fnmatch(basename, glob):
            return True
    # Dot-prefixed marker match
    for prefix in NEVER_TOUCH_PREFIXES:
        if basename.startswith(prefix):
            return True
    return False
