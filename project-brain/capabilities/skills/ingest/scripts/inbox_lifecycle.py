from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

from skills.ingest.scripts.inbox_unified_models import InboxArchiveMove, InboxArchivePlan


_VERSION_RE = re.compile(r"(?:^|[-_\s])v(\d+)(?:$|[-_\s])", re.IGNORECASE)


def _load_hygiene_apply():
    path = Path(__file__).resolve().parents[2] / "routine-vault" / "scripts" / "hygiene_apply.py"
    spec = importlib.util.spec_from_file_location("routine_vault_hygiene_apply_for_inbox", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load hygiene_apply from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.hygiene_apply


hygiene_apply = _load_hygiene_apply()


def _normalize_group(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", Path(value).stem.lower()).strip("-")


def _version_number(filename: str) -> int | None:
    match = _VERSION_RE.search(Path(filename).stem)
    return int(match.group(1)) if match else None


def _relative_path(folder: str, filename: str) -> str:
    return (Path(folder) / filename).as_posix() if folder else filename


def _milestone_names(folder: Path) -> set[str]:
    marker = folder / ".milestones.json"
    if not marker.is_file():
        return set()
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    names: set[str] = set()
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("milestones", [])
    else:
        entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw_path = entry.get("path") or entry.get("relative_path")
        if isinstance(raw_path, str) and raw_path:
            names.add(Path(raw_path).name)
    return names


def _outside_plan(target_folder: str) -> InboxArchivePlan:
    return InboxArchivePlan(
        refused=[
            InboxArchiveMove(
                relative_path=target_folder,
                reason="Target folder escapes docs root.",
                artifact_group="",
                status="refused",
                refusal_category="outside_docs_root",
            )
        ]
    )


def plan_version_archives(
    docs_root: Path,
    target_folder: str,
    version_group: str,
    final_filename: str,
) -> InboxArchivePlan:
    """Plan deterministic archives for obvious superseded versions in one folder."""
    resolved_docs = Path(docs_root).resolve()
    folder = (resolved_docs / target_folder).resolve()
    try:
        folder.relative_to(resolved_docs)
    except ValueError:
        return _outside_plan(target_folder)

    if not folder.is_dir():
        return InboxArchivePlan()

    incoming_version = _version_number(final_filename)
    normalized_group = _normalize_group(version_group)
    milestones = _milestone_names(folder)
    auto_archive: list[InboxArchiveMove] = []
    ask: list[InboxArchiveMove] = []
    refused: list[InboxArchiveMove] = []

    for item in sorted(folder.iterdir(), key=lambda path: path.name):
        if not item.is_file() or item.name == final_filename or item.name == ".milestones.json":
            continue
        normalized_stem = _normalize_group(item.stem)
        if not normalized_stem.startswith(normalized_group):
            continue
        rel = _relative_path(target_folder, item.name)
        if item.name in milestones:
            refused.append(
                InboxArchiveMove(
                    relative_path=rel,
                    reason=f"{item.name} is pinned as a milestone.",
                    artifact_group=version_group,
                    status="refused",
                    refusal_category="milestone_pinned",
                )
            )
            continue

        existing_version = _version_number(item.name)
        if incoming_version is not None and existing_version is not None:
            if existing_version < incoming_version:
                auto_archive.append(
                    InboxArchiveMove(
                        relative_path=rel,
                        reason=f"superseded by {final_filename}",
                        artifact_group=version_group,
                    )
                )
            elif existing_version == incoming_version:
                ask.append(
                    InboxArchiveMove(
                        relative_path=rel,
                        reason=f"same version as incoming {final_filename}",
                        artifact_group=version_group,
                        status="needs_input",
                        refusal_category="same_version_ambiguous",
                    )
                )
    return InboxArchivePlan(auto_archive=auto_archive, ask=ask, refused=refused)


def apply_archive_plan(docs_root: Path, plan: InboxArchivePlan, dry_run: bool = False) -> dict[str, Any]:
    move_payloads = [
        {
            "from": move.relative_path,
            "reason": move.reason,
            "artifact_group": move.artifact_group,
        }
        for move in plan.auto_archive
    ]
    return hygiene_apply(
        root="docs",
        moves=move_payloads,
        dry_run=dry_run,
        store_root=Path(docs_root).resolve(),
    )


__all__ = ["apply_archive_plan", "plan_version_archives"]
