"""Build Browse archive entries from Sweep archive manifests and ledgers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DOCS_RECOVERY_HINT = "Move the file out of its .archive folder to restore it."
GIT_RECOVERY_HINT = "Review git status and restore the archived path if needed."
GIT_HISTORY_PURGE_RECOVERY_HINT = (
    "Use the recovery command from the sweep ledger to restore this payload from git history."
)
ARCHIVE_MODE_ALIASES = {
    "docs-folder-archive": "docs-archive",
    "git-aware-archive": "git-aware",
}
VALID_SOURCE_TABS = {"sources", "notes", "pages", "skills"}


def _safe_id(value: str) -> str:
    return value.replace("\\", "/")


def _canonical_archive_mode(value: object, default: str) -> str:
    mode = str(value or default)
    return ARCHIVE_MODE_ALIASES.get(mode, mode)


def _string_or_empty(value: object) -> str:
    return "" if value is None else str(value)


def _add_warning(
    warnings: list[dict[str, Any]],
    *,
    kind: str,
    path: Path,
    line: int | None = None,
    field: str | None = None,
    detail: str = "",
) -> None:
    warning: dict[str, Any] = {
        "kind": kind,
        "path": str(path),
    }
    if line is not None:
        warning["line"] = line
    if field:
        warning["field"] = field
    if detail:
        warning["detail"] = detail
    warnings.append(warning)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _has_symlink_between(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _has_parent_reference(path: Path) -> bool:
    return ".." in path.parts


def _resolve_docs_path(
    *,
    root: Path,
    raw_value: object,
    field: str,
    warning_path: Path,
    line_no: int,
    warnings: list[dict[str, Any]],
) -> Path | None:
    raw_path = str(raw_value or "")
    if not raw_path:
        _add_warning(warnings, kind="missing_path", path=warning_path, line=line_no, field=field)
        return None

    relative_path = Path(raw_path)
    if relative_path.is_absolute() or _has_parent_reference(relative_path):
        _add_warning(warnings, kind="unsafe_path", path=warning_path, line=line_no, field=field)
        return None

    resolved = (root / relative_path).resolve(strict=False)
    if not _is_relative_to(resolved, root):
        _add_warning(warnings, kind="unsafe_path", path=warning_path, line=line_no, field=field)
        return None

    if _has_symlink_between(root, root / relative_path):
        _add_warning(warnings, kind="unsafe_path", path=warning_path, line=line_no, field=field)
        return None

    return resolved


def _iter_docs_manifests(
    documents_root: Path,
    warnings: list[dict[str, Any]],
) -> list[Path]:
    if not documents_root.is_dir():
        return []

    manifests: list[Path] = []
    for archive_dir in sorted(documents_root.rglob(".archive")):
        if archive_dir.is_symlink():
            _add_warning(warnings, kind="unsafe_manifest", path=archive_dir)
            continue
        if not archive_dir.is_dir():
            continue
        resolved_archive = archive_dir.resolve(strict=False)
        if not _is_relative_to(resolved_archive, documents_root):
            _add_warning(warnings, kind="unsafe_manifest", path=archive_dir)
            continue
        if _has_symlink_between(documents_root, archive_dir):
            _add_warning(warnings, kind="unsafe_manifest", path=archive_dir)
            continue

        manifest = archive_dir / "_manifest.jsonl"
        if manifest.is_symlink():
            _add_warning(warnings, kind="unsafe_manifest", path=manifest)
            continue
        if manifest.is_file():
            manifests.append(manifest)
    return manifests


def _docs_entry(
    *,
    documents_root: Path,
    manifest: Path,
    line_no: int,
    item: dict[str, Any],
    warnings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    original_rel = str(item.get("from") or "")
    archived_rel = str(item.get("to") or "")
    original_path = _resolve_docs_path(
        root=documents_root,
        raw_value=original_rel,
        field="from",
        warning_path=manifest,
        line_no=line_no,
        warnings=warnings,
    )
    archived_path = _resolve_docs_path(
        root=documents_root,
        raw_value=archived_rel,
        field="to",
        warning_path=manifest,
        line_no=line_no,
        warnings=warnings,
    )
    if original_path is None or archived_path is None:
        return None

    run_id = str(item.get("apply_run_id") or "unknown")
    reason = _string_or_empty(item.get("reason")) or "Archived by Sweep"
    source_tab = str(item.get("source_tab") or "sources")
    if source_tab not in VALID_SOURCE_TABS:
        source_tab = "sources"
    name = Path(original_rel).name or Path(archived_rel).name

    return {
        "id": f"sweep:docs:{run_id}:{_safe_id(original_rel)}",
        "type": "vault",
        "name": name,
        "title": name,
        "description": reason,
        "hub": "system",
        "source_path": str(archived_path),
        "journey_category": "archive",
        "archive_source": "sweep",
        "archive_mode": "docs-archive",
        "source_tab": source_tab,
        "original_path": str(original_path),
        "archived_path": str(archived_path),
        "reason": _string_or_empty(item.get("reason")),
        "artifact_group": _string_or_empty(item.get("artifact_group")),
        "apply_run_id": run_id,
        "archived_at": _string_or_empty(item.get("archived_at")),
        "recovery_hint": _string_or_empty(item.get("recovery_hint")) or DOCS_RECOVERY_HINT,
    }


def _collect_docs_archive_entries(
    documents_dir: Path,
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    documents_root = Path(documents_dir).expanduser().resolve(strict=False)
    entries: list[dict[str, Any]] = []
    for manifest in _iter_docs_manifests(documents_root, warnings):
        try:
            lines = manifest.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            _add_warning(warnings, kind="read_error", path=manifest, detail=str(exc))
            continue

        for line_no, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                _add_warning(
                    warnings,
                    kind="malformed_json",
                    path=manifest,
                    line=line_no,
                    detail=str(exc),
                )
                continue
            if not isinstance(item, dict):
                _add_warning(warnings, kind="malformed_record", path=manifest, line=line_no)
                continue
            entry = _docs_entry(
                documents_root=documents_root,
                manifest=manifest,
                line_no=line_no,
                item=item,
                warnings=warnings,
            )
            if entry is not None:
                entries.append(entry)
    return entries


def docs_archive_entries(documents_dir: Path) -> list[dict[str, Any]]:
    """Return Browse-shaped entries for per-folder docs archive manifests."""
    warnings: list[dict[str, Any]] = []
    return _collect_docs_archive_entries(documents_dir, warnings)


def _ledger_paths(root: Path, warnings: list[dict[str, Any]]) -> list[Path]:
    ledger_root = Path(root).expanduser()
    if ledger_root.is_symlink():
        _add_warning(warnings, kind="unsafe_ledger", path=ledger_root)
        return []
    if not ledger_root.exists():
        return []
    if ledger_root.is_file():
        if ledger_root.is_symlink():
            _add_warning(warnings, kind="unsafe_ledger", path=ledger_root)
            return []
        if ledger_root.name == "sweep-ledger.jsonl":
            return [ledger_root]
        if ledger_root.name == "sweep.jsonl" and ledger_root.parent.name == "_ledger":
            return [ledger_root]
        return []

    ledgers: list[Path] = []
    new_ledger = ledger_root / "_ledger" / "sweep.jsonl"
    if new_ledger.exists():
        if new_ledger.is_symlink() or _has_symlink_between(ledger_root, new_ledger):
            _add_warning(warnings, kind="unsafe_ledger", path=new_ledger)
        elif new_ledger.is_file():
            ledgers.append(new_ledger)
    for path in sorted(ledger_root.rglob("sweep-ledger.jsonl")):
        if path.is_symlink() or _has_symlink_between(ledger_root, path):
            _add_warning(warnings, kind="unsafe_ledger", path=path)
            continue
        if path.is_file():
            ledgers.append(path)
    return ledgers


def _infer_repository_root(ledger: Path) -> Path | None:
    parts = ledger.resolve(strict=False).parts
    for index in range(len(parts) - 1):
        if parts[index] == "archive" and index + 1 < len(parts) and parts[index + 1] == "sweep":
            if index == 0:
                return None
            return Path(*parts[:index])
        if parts[index] == "archive" and index + 1 < len(parts) and parts[index + 1] == "_ledger":
            if index == 0:
                return None
            return Path(*parts[:index])
    return None


def _repository_root_from_ledger(
    *,
    ledger: Path,
    item: dict[str, Any],
    line_no: int,
    warnings: list[dict[str, Any]],
) -> Path | None:
    inferred_root = _infer_repository_root(ledger)
    repository_raw = str(item.get("repository_root") or item.get("repo_root") or "")
    if not repository_raw:
        return inferred_root

    repository_path = Path(repository_raw).expanduser()
    if (
        not repository_path.is_absolute()
        or _has_parent_reference(repository_path)
        or repository_path.is_symlink()
    ):
        _add_warning(
            warnings,
            kind="unsafe_path",
            path=ledger,
            line=line_no,
            field="repository_root",
        )
        return None

    repository_root = repository_path.resolve(strict=False)
    if inferred_root is not None and repository_root != inferred_root.resolve(strict=False):
        _add_warning(
            warnings,
            kind="unsafe_path",
            path=ledger,
            line=line_no,
            field="repository_root",
            detail="Ledger repository_root does not match the ledger location.",
        )
        return None
    return repository_root


def _resolve_ledger_path(
    *,
    raw_path: object,
    repository_root: Path | None,
    ledger: Path,
    line_no: int,
    field: str,
    warnings: list[dict[str, Any]],
) -> str | None:
    value = str(raw_path or "")
    if not value:
        return ""
    path = Path(value)
    if _has_parent_reference(path):
        _add_warning(warnings, kind="unsafe_path", path=ledger, line=line_no, field=field)
        return None
    if repository_root is None:
        _add_warning(
            warnings,
            kind="unsafe_path",
            path=ledger,
            line=line_no,
            field=field,
            detail="Ledger path cannot be validated without a repository root.",
        )
        return None

    candidate = path.expanduser() if path.is_absolute() else repository_root / path
    resolved = candidate.resolve(strict=False)
    if not _is_relative_to(resolved, repository_root):
        _add_warning(warnings, kind="unsafe_path", path=ledger, line=line_no, field=field)
        return None
    if _has_symlink_between(repository_root, candidate):
        _add_warning(warnings, kind="unsafe_path", path=ledger, line=line_no, field=field)
        return None
    return str(resolved)


def _source_tab_from_ledger(item: dict[str, Any], archived_path: str) -> str:
    source_tab = str(item.get("source_tab") or "")
    if source_tab in VALID_SOURCE_TABS:
        return source_tab
    parts = Path(archived_path).parts
    for index, part in enumerate(parts[:-1]):
        if part == "sweep" and index > 0 and parts[index - 1] == "archive":
            candidate = parts[index + 1] if index + 1 < len(parts) else ""
            if candidate in VALID_SOURCE_TABS:
                return candidate
    return "sources"


def _git_action_from_ledger(item: dict[str, Any], archive_mode: str, archived_raw: object) -> str:
    git_action = item.get("git_action")
    if git_action not in (None, ""):
        return str(git_action)
    if archive_mode == "git-aware" and archived_raw:
        return "mv"
    return ""


def _ledger_entry(
    *,
    ledger: Path,
    line_no: int,
    item: dict[str, Any],
    warnings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    repository_root = _repository_root_from_ledger(
        ledger=ledger,
        item=item,
        line_no=line_no,
        warnings=warnings,
    )

    archive_mode = _canonical_archive_mode(item.get("archive_mode"), "git-aware")
    original_raw = item.get("relative_path") or item.get("from") or item.get("original_path") or ""
    archived_raw = item.get("archived_path") or item.get("to") or ""
    if not any(
        str(item.get(field) or "").strip()
        for field in ("original_path", "relative_path", "from")
    ):
        _add_warning(
            warnings,
            kind="malformed_record",
            path=ledger,
            line=line_no,
            field="original_path",
            detail="Ledger record is missing original_path/relative_path/from.",
        )
        return None
    if not archived_raw:
        _add_warning(
            warnings,
            kind="malformed_record",
            path=ledger,
            line=line_no,
            field="archived_path",
            detail="Ledger record is missing archived_path/to.",
        )
        return None

    source_path = _resolve_ledger_path(
        raw_path=archived_raw,
        repository_root=repository_root,
        ledger=ledger,
        line_no=line_no,
        field="archived_path" if item.get("archived_path") else "to",
        warnings=warnings,
    )
    if source_path is None:
        return None

    original_path = _resolve_ledger_path(
        raw_path=item.get("original_path") or original_raw,
        repository_root=repository_root,
        ledger=ledger,
        line_no=line_no,
        field="original_path"
        if item.get("original_path")
        else "relative_path"
        if item.get("relative_path")
        else "from",
        warnings=warnings,
    )
    if original_path is None:
        return None
    archived_path = source_path
    if not original_raw and original_path:
        original_raw = original_path

    run_id = str(item.get("apply_run_id") or "unknown")
    id_path = str(item.get("relative_path") or item.get("from") or original_raw or archived_raw)
    name = Path(str(id_path or archived_raw)).name
    reason = _string_or_empty(item.get("reason")) or "Archived by Sweep"
    source_tab = _source_tab_from_ledger(item, str(archived_raw))
    repository_root_value = str(repository_root) if repository_root is not None else ""
    git_action = _git_action_from_ledger(item, archive_mode, archived_raw)

    return {
        "id": f"sweep:{archive_mode}:{run_id}:{_safe_id(str(id_path))}",
        "type": "vault",
        "name": name,
        "title": name,
        "description": reason,
        "hub": "system",
        "source_path": source_path,
        "journey_category": "archive",
        "archive_source": "sweep",
        "archive_mode": archive_mode,
        "source_tab": source_tab,
        "original_path": original_path,
        "archived_path": archived_path,
        "repo_root": repository_root_value,
        "repository_root": repository_root_value,
        "git_action": git_action,
        "reason": _string_or_empty(item.get("reason")),
        "artifact_group": _string_or_empty(item.get("artifact_group")),
        "apply_run_id": run_id,
        "archived_at": _string_or_empty(item.get("archived_at")),
        "recovery_hint": _string_or_empty(item.get("recovery_hint")) or GIT_RECOVERY_HINT,
    }


def _is_git_history_purge_ledger(ledger: Path) -> bool:
    return ledger.name == "sweep.jsonl" and ledger.parent.name == "_ledger"


def _read_git_history_purge_events(
    *,
    ledger: Path,
    warnings: list[dict[str, Any]],
) -> list[tuple[int, dict[str, Any]]]:
    try:
        lines = ledger.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _add_warning(warnings, kind="read_error", path=ledger, detail=str(exc))
        return []

    events: list[tuple[int, dict[str, Any]]] = []
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            _add_warning(
                warnings,
                kind="malformed_json",
                path=ledger,
                line=line_no,
                detail=str(exc),
            )
            continue
        if not isinstance(item, dict):
            _add_warning(warnings, kind="malformed_record", path=ledger, line=line_no)
            continue
        if item.get("event") in {"archive_prepared", "purged"}:
            events.append((line_no, item))
    return events


def _collect_git_history_purge_entries(
    *,
    ledger: Path,
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for line_no, event in _read_git_history_purge_events(ledger=ledger, warnings=warnings):
        archive_record_id = str(event.get("archive_record_id") or "")
        if not archive_record_id:
            _add_warning(
                warnings,
                kind="malformed_record",
                path=ledger,
                line=line_no,
                field="archive_record_id",
            )
            continue
        grouped.setdefault(archive_record_id, []).append((line_no, event))

    entries: list[dict[str, Any]] = []
    repository_root = _infer_repository_root(ledger)
    for archive_record_id, events in grouped.items():
        prepared = next((event for _line_no, event in events if event.get("event") == "archive_prepared"), None)
        if prepared is None:
            _add_warning(
                warnings,
                kind="malformed_record",
                path=ledger,
                field="archive_prepared",
                detail=f"Missing archive_prepared event for {archive_record_id}.",
            )
            continue
        prepared_line = next(line_no for line_no, event in events if event is prepared)
        purged = next(
            (event for _line_no, event in reversed(events) if event.get("event") == "purged"),
            None,
        )
        entry = _git_history_purge_entry(
            ledger=ledger,
            line_no=prepared_line,
            archive_record_id=archive_record_id,
            prepared=prepared,
            purged=purged,
            repository_root=repository_root,
            warnings=warnings,
        )
        if entry is not None:
            entries.append(entry)
    return entries


def _git_history_purge_entry(
    *,
    ledger: Path,
    line_no: int,
    archive_record_id: str,
    prepared: dict[str, Any],
    purged: dict[str, Any] | None,
    repository_root: Path | None,
    warnings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    original_raw = prepared.get("original_path") or prepared.get("relative_path") or prepared.get("from") or ""
    archived_raw = prepared.get("archived_path") or prepared.get("to") or ""
    if not original_raw:
        _add_warning(
            warnings,
            kind="malformed_record",
            path=ledger,
            line=line_no,
            field="original_path",
        )
        return None
    if not archived_raw:
        _add_warning(
            warnings,
            kind="malformed_record",
            path=ledger,
            line=line_no,
            field="archived_path",
        )
        return None

    archived_path = _resolve_ledger_path(
        raw_path=archived_raw,
        repository_root=repository_root,
        ledger=ledger,
        line_no=line_no,
        field="archived_path",
        warnings=warnings,
    )
    original_path = _resolve_ledger_path(
        raw_path=original_raw,
        repository_root=repository_root,
        ledger=ledger,
        line_no=line_no,
        field="original_path",
        warnings=warnings,
    )
    if archived_path is None or original_path is None:
        return None

    run_id = str(prepared.get("apply_run_id") or "unknown")
    reason = _string_or_empty(prepared.get("reason")) or "Archived by Sweep"
    name = Path(str(original_raw or archived_raw)).name
    source_tab = _source_tab_from_ledger(prepared, str(archived_raw))
    repository_root_value = str(repository_root) if repository_root is not None else ""
    is_purged = purged is not None
    archive_commit = _string_or_empty(purged.get("archive_commit")) if purged else ""
    recovery_hint = (
        _string_or_empty(purged.get("recovery_hint"))
        if purged
        else _string_or_empty(prepared.get("recovery_hint"))
    )

    return {
        "id": f"sweep:git-history-purge:{run_id}:{_safe_id(str(original_raw))}",
        "type": "vault",
        "name": name,
        "title": name,
        "description": reason,
        "hub": "system",
        "source_path": archived_path,
        "journey_category": "archive",
        "archive_source": "sweep",
        "archive_mode": "git-history-purge",
        "source_tab": source_tab,
        "original_path": original_path,
        "archived_path": archived_path,
        "repo_root": repository_root_value,
        "repository_root": repository_root_value,
        "git_action": "mv+purge",
        "reason": _string_or_empty(prepared.get("reason")),
        "artifact_group": _string_or_empty(prepared.get("artifact_group")),
        "apply_run_id": run_id,
        "archived_at": _string_or_empty(prepared.get("archived_at")),
        "ledger_path": str(ledger),
        "archive_record_id": archive_record_id,
        "brain_id": _string_or_empty(prepared.get("brain_id") or (purged or {}).get("brain_id")),
        "source_kind": _string_or_empty(prepared.get("source_kind") or prepared.get("kind")),
        "purged": is_purged,
        "archive_commit": archive_commit,
        "archive_pushed": bool(purged.get("archive_pushed")) if purged else False,
        "purged_at": _string_or_empty(purged.get("purged_at")) if purged else "",
        "recovery_hint": recovery_hint or GIT_HISTORY_PURGE_RECOVERY_HINT,
    }


def _collect_ledger_entries(
    ledger_roots: list[Path],
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for root in ledger_roots:
        for ledger in _ledger_paths(root, warnings):
            if _is_git_history_purge_ledger(ledger):
                entries.extend(_collect_git_history_purge_entries(ledger=ledger, warnings=warnings))
                continue
            try:
                lines = ledger.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                _add_warning(warnings, kind="read_error", path=ledger, detail=str(exc))
                continue

            for line_no, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    _add_warning(
                        warnings,
                        kind="malformed_json",
                        path=ledger,
                        line=line_no,
                        detail=str(exc),
                    )
                    continue
                if not isinstance(item, dict):
                    _add_warning(warnings, kind="malformed_record", path=ledger, line=line_no)
                    continue
                entry = _ledger_entry(ledger=ledger, line_no=line_no, item=item, warnings=warnings)
                if entry is not None:
                    entries.append(entry)
    return entries


def collect_sweep_archive_entries(
    *,
    documents_dir: Path,
    ledger_roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Collect Sweep archive entries and warning metadata for Browse."""
    warnings: list[dict[str, Any]] = []
    entries = [
        *_collect_docs_archive_entries(documents_dir, warnings),
        *_collect_ledger_entries(ledger_roots or [], warnings),
    ]
    return {
        "entries": entries,
        "warning_count": len(warnings),
        "warnings": warnings,
    }
