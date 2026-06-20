"""List vault notes across all skills in a hub."""

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


def _build_note_entry(note_path: Path, skill_root: Path, skill_name: str) -> dict:
    stat = note_path.stat()
    content = note_path.read_text(encoding="utf-8", errors="replace")
    body = content

    if content.startswith("---"):
        end = content.find("\n---", 4)
        if end != -1:
            body = content[end + 4 :].lstrip("\n")

    entry = {
        "name": str(note_path.relative_to(skill_root)),
        "skill": skill_name,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "preview": body[:500].strip(),
        "_mtime": stat.st_mtime,
    }
    brain_id = _resolve_note_brain_id(note_path)
    if brain_id:
        entry["brain_id"] = brain_id
    return entry


def _resolve_note_brain_id(note_path: Path) -> str | None:
    """Owning brain for a vault note (ADR-772), best-effort."""
    try:
        from src.lib.brain_path import resolve_brain_id_for_path

        return resolve_brain_id_for_path(note_path)
    except Exception:
        return None


async def list_hub_vault_notes_impl(
    hub_id: str,
    skill_names: list[str],
    vault_dir: Path,
    limit: int = 50,
    per_skill_limit: int = 8,
) -> str:
    """List recent vault notes across all skills belonging to a hub."""
    all_notes: list[dict] = []

    for skill_name in skill_names:
        skill_notes: list[dict] = []
        seen: set[Path] = set()

        for skill_root in _resolve_skill_roots(vault_dir, skill_name):
            if not skill_root.is_dir():
                continue
            for pattern in ("*.md", "*/*.md", "*/*/*.md", "*/*/*/*.md"):
                for note_path in skill_root.glob(pattern):
                    if not note_path.is_file() or note_path in seen:
                        continue
                    if any(part.startswith(".") for part in note_path.relative_to(skill_root).parts):
                        continue
                    seen.add(note_path)
                    skill_notes.append(_build_note_entry(note_path, skill_root, skill_name))

        skill_notes.sort(key=lambda note: note["_mtime"], reverse=True)
        all_notes.extend(skill_notes[:per_skill_limit])

    all_notes.sort(key=lambda note: note["_mtime"], reverse=True)
    result_notes = all_notes[:limit]

    for note in result_notes:
        del note["_mtime"]

    return json.dumps({"success": True, "hub_id": hub_id, "notes": result_notes, "count": len(result_notes)})
