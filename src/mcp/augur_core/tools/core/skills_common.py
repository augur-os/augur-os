"""
Shared helpers and constants for the skill discovery tool implementations.

Leaf module: imported by the skills_* impl modules. Imports no sibling
skills_* module to keep the dependency graph acyclic.
"""

import re
from pathlib import Path

GENERATED_DOC_MARKER = "AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY"
GENERATED_CLIENT_DIRS = {".claude", ".codex", ".cursor", ".gemini"}


def _resolve_skill_note_brain_id(md_file: Path) -> str | None:
    """Owning brain for a skill vault note (ADR-772), best-effort."""
    try:
        from src.lib.brain_path import resolve_brain_id_for_path

        return resolve_brain_id_for_path(md_file)
    except Exception:
        return None


def _is_generated_skill_doc(skill_md: Path, content: str) -> bool:
    parts = set(skill_md.parts)
    if parts.intersection(GENERATED_CLIENT_DIRS):
        return True
    return GENERATED_DOC_MARKER in content[:2048]


def _generated_source_path(content: str) -> str | None:
    match = re.search(r"^\s*Source:\s*(.+?)\s*$", content, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _strip_generated_header(markdown: str) -> str:
    stripped = markdown.lstrip()
    if not stripped.startswith("<!--"):
        return markdown.strip()

    comment_end = stripped.find("-->")
    if comment_end == -1:
        return markdown.strip()

    comment = stripped[: comment_end + 3]
    if GENERATED_DOC_MARKER not in comment:
        return markdown.strip()

    return stripped[comment_end + 3 :].strip()


def _get_skills_dir() -> Path:
    """Get the canonical skills directory."""
    from src.mcp.augur_shared.config import get_config

    return get_config().plugins_dir


def _get_data_dir() -> Path:
    """Get the project root directory."""
    from src.mcp.augur_shared.config import get_project_root

    return get_project_root()
