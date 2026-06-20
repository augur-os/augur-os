"""Detect skill copies that should not be treated as masters.

Augur's sync pipeline generates client-specific copies of master skills under
`.claude/skills/`, `.gemini/skills/`, etc. These copies carry markers so the
registry can distinguish them from real master skills:

  - ``<!-- AUGUR-ADAPTED-COPY source=<client> -->`` — full body copy adapted
    for a specific client surface.
  - ``<!-- AUGUR-STUB`` — placeholder pointing back at the master via
    ``get-skill``; never carries real content.
  - ``<!-- AUTO-GENERATED FILE -->`` — legacy marker still found in older
    generated artifacts.

A SKILL.md carrying any of these markers is **not** a master skill and must
not shadow a true master in registry resolution.
"""

from __future__ import annotations

from pathlib import Path

_ADAPTED_MARKERS: tuple[str, ...] = (
    "AUGUR-ADAPTED-COPY",
    "AUGUR-STUB",
    "AUTO-GENERATED FILE",
)


def is_adapted_copy(skill_md: Path) -> bool:
    """Return ``True`` if ``skill_md`` is a generated/adapted copy, not a master.

    Returns ``False`` for missing files, empty files, and master content
    without any recognised marker.
    """
    try:
        text = skill_md.read_text()
    except (FileNotFoundError, IsADirectoryError, OSError):
        return False
    if not text:
        return False
    return any(marker in text for marker in _ADAPTED_MARKERS)
