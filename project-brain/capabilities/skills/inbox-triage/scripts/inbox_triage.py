"""Pure logic for daily vault-inbox triage (auto-file capture cards).

Enumerate cards in the vault inbox (``brain_capture_dir``) and atomically file
one card into a target vault domain — move + provenance frontmatter + Browse
index refresh. Move-only; never deletes. Classification judgment lives in the
client session, not here.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.lib.brain_layout import brain_capture_dir, is_machine_path
from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter
from skills.ingest.scripts.slug_policy import capture_slug, unique_name
from src.lib.ingest.note_index_refresh import refresh_browse_after_write


_EXCERPT_CHARS = 400


def _age_days(captured_at: Any, mtime: float) -> int:
    if isinstance(captured_at, str):
        try:
            dt = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:  # naive timestamps (older cards) → assume UTC
                dt = dt.replace(tzinfo=UTC)
            return max(0, (datetime.now(UTC) - dt).days)
        except ValueError:
            pass
    return max(0, (datetime.now(UTC) - datetime.fromtimestamp(mtime, UTC)).days)


def list_inbox_cards(vault_dir: Path) -> list[dict[str, Any]]:
    """Enumerate vault-inbox ``*.md`` cards with classification metadata."""
    inbox = brain_capture_dir(vault_dir)
    if not inbox.is_dir():
        return []
    cards: list[dict[str, Any]] = []
    for path in sorted(inbox.glob("*.md")):
        try:
            meta, body = parse_frontmatter(path)
        except Exception:
            meta, body = {}, path.read_text(encoding="utf-8", errors="replace")
        excerpt = " ".join(body.split())[:_EXCERPT_CHARS]
        cards.append(
            {
                "path": str(path),
                "title": str(meta.get("title") or path.stem),
                "note_type": str(meta.get("x-augur-note-type") or "unknown"),
                "excerpt": excerpt,
                "age_days": _age_days(meta.get("captured_at"), path.stat().st_mtime),
            }
        )
    return cards


def _resolve_target_dir(vault_dir: Path, target_rel: str) -> tuple[Path | None, str]:
    """Resolve a target dir under the vault, rejecting unsafe targets.

    Returns (resolved_dir, "") on success or (None, error_message) on rejection.
    """
    rel = target_rel.strip().strip("/")
    if not rel:
        return None, "empty target"
    candidate = (vault_dir / rel).resolve()
    vault_resolved = vault_dir.resolve()
    if vault_resolved not in candidate.parents and candidate != vault_resolved:
        return None, f"target resolves outside vault: {target_rel}"
    if is_machine_path(vault_dir, candidate):
        return None, f"target is a machine path: {target_rel}"
    return candidate, ""


def file_card(
    *,
    vault_dir: Path,
    card_path: Path,
    target_rel: str,
    reason: str,
    refresh_index: bool = True,
) -> dict[str, Any]:
    """Atomically file one inbox card into ``target_rel``. Move-only.

    Adds provenance frontmatter, creates the target folder if missing, and
    (unless ``refresh_index`` is False) refreshes the Browse index. Never
    deletes content; guards reject targets outside the vault or inside machine
    dirs.
    """
    card_path = Path(card_path)
    inbox = brain_capture_dir(vault_dir).resolve()
    if card_path.resolve().parent != inbox:
        return {"success": False, "error": f"card is not in the vault inbox: {card_path}"}
    if not card_path.is_file():
        return {"success": False, "error": f"card not found: {card_path}"}

    target_dir, err = _resolve_target_dir(vault_dir, target_rel)
    if target_dir is None:
        return {"success": False, "error": err}

    created_folder = not target_dir.exists()
    target_dir.mkdir(parents=True, exist_ok=True)

    stem = unique_name(target_dir, capture_slug(card_path.stem))
    new_path = target_dir / f"{stem}.md"

    meta, body = parse_frontmatter(card_path)
    rel_target = str(target_dir.resolve().relative_to(vault_dir.resolve()))
    provenance = {
        "filed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "filed_to": rel_target,
        "filed_by": "inbox-triage",
        "filed_reason": reason,
    }
    if created_folder:
        provenance["filed_created_folder"] = True
    # unique_name guarantees a fresh path, so write_vault_frontmatter writes a
    # new file; re-apply the card's existing meta first, then provenance.
    merged = {**meta, **provenance}
    write_vault_frontmatter(new_path, merged, body.rstrip() + "\n")
    card_path.unlink()  # move = write new + remove old; both inside the vault

    result: dict[str, Any] = {
        "success": True,
        "new_path": str(new_path),
        "filed_to": rel_target,
        "created_folder": created_folder,
        "reason": reason,
    }
    if refresh_index:
        try:
            # Map the NEW path so a moved prompt card also refreshes "prompts".
            statuses = refresh_browse_after_write(paths=[new_path], vault_dir=vault_dir)
            result["browse_index"] = {cat: s.to_dict() for cat, s in statuses.items()}
        except Exception as exc:  # index refresh failure must not lose the move
            result["browse_index"] = {"success": False, "error": str(exc)}
    return result
