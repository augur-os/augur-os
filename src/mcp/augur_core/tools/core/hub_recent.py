"""List recent files across all skills in a hub."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_skill_vault_relative_dir
from src.lib.brain_layout import join_brain_relative


def _resolve_skill_roots(vault_dir: Path, skill_name: str) -> list[Path]:
    """Return active vault roots for a skill under an injected vault root."""
    primary = join_brain_relative(vault_dir, get_skill_vault_relative_dir(skill_name))
    roots = [primary]
    legacy = vault_dir / skill_name
    try:
        same_dir = legacy.resolve() == primary.resolve()
    except OSError:
        same_dir = legacy == primary
    if legacy.exists() and not same_dir:
        roots.append(legacy)
    return roots


async def list_hub_recent_files_impl(
    hub_id: str,
    skill_names: list[str],
    vault_dir: Path,
    limit: int = 10,
    per_skill_limit: int = 2,
) -> str:
    """List recent vault files across all skills belonging to a hub.

    Scans vault directories for each skill, collects files, sorts by
    modification time, and caps per-skill to prevent domination.

    Args:
        hub_id: Hub identifier (e.g., "career").
        skill_names: List of skill names belonging to this hub.
        vault_dir: Root vault directory.
        limit: Maximum total files to return.
        per_skill_limit: Maximum files per skill.

    Returns:
        JSON string with {success, files, count}.
    """
    all_files: list[dict] = []

    for skill_name in skill_names:
        skill_files: list[dict] = []
        # Collect files up to 2 levels deep
        seen: set[Path] = set()
        for skill_vault in _resolve_skill_roots(vault_dir, skill_name):
            if not skill_vault.is_dir():
                continue
            for pattern in ("*", "*/*"):
                for p in skill_vault.glob(pattern):
                    if not p.is_file() or p in seen:
                        continue
                    # Skip hidden files and directories
                    if any(part.startswith(".") for part in p.relative_to(skill_vault).parts):
                        continue
                    seen.add(p)

                    stat = p.stat()
                    is_markdown = p.suffix.lower() in (".md", ".markdown")
                    file_type = "note" if is_markdown else "doc"

                    # Build preview for markdown files
                    preview = ""
                    if is_markdown:
                        try:
                            content = p.read_text(encoding="utf-8", errors="replace")
                            body = content
                            if content.startswith("---"):
                                end = content.find("\n---", 4)
                                if end != -1:
                                    body = content[end + 4 :].lstrip("\n")
                            preview = body[:200].strip()
                        except OSError:
                            pass

                    skill_files.append(
                        {
                            "name": p.name,
                            "path": p.relative_to(vault_dir).as_posix(),
                            "type": file_type,
                            "skill": skill_name,
                            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                            "preview": preview,
                            "_mtime": stat.st_mtime,
                        }
                    )

        # Sort skill files by mtime descending, cap per skill
        skill_files.sort(key=lambda f: f["_mtime"], reverse=True)
        all_files.extend(skill_files[:per_skill_limit])

    # Sort all collected files by mtime descending, cap total
    all_files.sort(key=lambda f: f["_mtime"], reverse=True)
    result_files = all_files[:limit]

    # Remove internal _mtime key before returning
    for f in result_files:
        del f["_mtime"]

    return json.dumps({"success": True, "files": result_files, "count": len(result_files)})
