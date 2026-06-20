"""Orchestration helpers for /note capture flows."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from src.lib.ingest.note_index_refresh import refresh_notes_browse_index
from skills.ingest.scripts.thought_cards import (
    compute_thought_hash,
    find_existing_thought_card,
    write_thought_card,
)


def save_thought_note(
    *,
    vault_dir: Path | None = None,
    body: str,
    title: str = "",
    captured_at: datetime | None = None,
    to: str | None = None,
    cwd: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, object]:
    """Persist a thought note and refresh Browse for new writes."""
    if not body.strip():
        return {"success": False, "error": "body is required"}

    brain_summary: dict[str, str] | None = None
    if to is not None or cwd is not None or registry_path is not None:
        from src.lib.brain_write_routing import resolve_write_target

        try:
            target = resolve_write_target(
                explicit_brain=to,
                cwd=cwd,
                registry_path=registry_path,
            )
        except KeyError as exc:
            return {"success": False, "error": str(exc)}
        if target.mode == "packet":
            return {
                "success": False,
                "error": f"brain {target.brain.id} requires packet-based writes",
                "brain": target.summary(),
                "packet_root": str(target.packet_root),
            }
        vault_dir = target.notes_vault_dir
        brain_summary = target.summary()

    if vault_dir is None:
        return {"success": False, "error": "vault_dir is required"}

    content_hash = compute_thought_hash(body)
    existing = find_existing_thought_card(vault_dir, content_hash)
    if existing is not None:
        result: dict[str, object] = {
            "success": True,
            "path": str(existing),
            "sha256": content_hash,
            "deduplicated": True,
        }
        if brain_summary is not None:
            result["brain"] = brain_summary
        return result

    path = write_thought_card(
        vault_dir=vault_dir,
        body=body,
        title=title,
        captured_at=captured_at or datetime.now(UTC),
    )
    browse_index = refresh_notes_browse_index(vault_dir=vault_dir)
    result: dict[str, object] = {
        "success": True,
        "path": str(path),
        "sha256": content_hash,
        "deduplicated": False,
        "browse_index": browse_index.to_dict(),
    }
    if brain_summary is not None:
        result["brain"] = brain_summary
    return result


__all__ = ["save_thought_note"]
