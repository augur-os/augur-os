"""Sweep archive + staged-leftover draft browse entries and their caches."""

import threading
import time as _time
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import (
    get_documents_dir,
    get_project_brain_skills_dir,
    get_project_root,
    get_runtime_dir,
    get_vault_dir,
)

from .index_paths import (
    _has_symlink_between,
    _path_identity,
    _path_lexical_identity,
    _path_lstat_mtime_ns,
    _path_mtime_ns,
)

_SWEEP_ARCHIVE_CACHE_TTL = 1.0
_SWEEP_ARCHIVE_MODULE_NAME = "loop_hygiene_archive_index"
_SWEEP_ARCHIVE_MODULE_PATH_ATTR = "__augur_source_path__"
_SWEEP_ARCHIVE_MODULE_MTIME_ATTR = "__augur_source_mtime_ns__"
_sweep_archive_cache_lock = threading.Lock()
_sweep_archive_cache_key: tuple[object, ...] | None = None
_sweep_archive_cache_entries: list[dict] = []
_sweep_archive_cache_ts: float = 0.0


def _format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)}B"
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{num_bytes}B"


def _directory_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _staging_batch_title(batch_name: str) -> str:
    if batch_name.startswith("client-leftovers-"):
        suffix = batch_name.removeprefix("client-leftovers-").replace("-", " ")
        return f"Client leftovers {suffix}"
    return batch_name.replace("-", " ").title()


def _staged_leftover_draft_entries() -> list[dict]:
    staging_root = get_runtime_dir() / "staging"
    if not staging_root.is_dir():
        return []

    entries: list[dict] = []
    for batch_dir in sorted(staging_root.glob("client-leftovers-*")):
        if not batch_dir.is_dir():
            continue
        skill_paths = sorted(batch_dir.rglob("SKILL.md"))
        if not skill_paths:
            continue

        clients = sorted(
            {path.relative_to(batch_dir).parts[0] for path in skill_paths if path.relative_to(batch_dir).parts}
        )
        try:
            staged_at = datetime.fromtimestamp(batch_dir.stat().st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            staged_at = ""
        size_bytes = _directory_size(batch_dir)
        entries.append(
            {
                "id": f"runtime-staging:{batch_dir.name}",
                "type": "vault",
                "name": batch_dir.name,
                "title": _staging_batch_title(batch_dir.name),
                "description": (
                    f"Recoverable client leftovers staged from {', '.join(clients) or 'client'} "
                    f"with {len(skill_paths)} skill file(s), {_format_size(size_bytes)} total."
                ),
                "hub": "system",
                "source_path": str(batch_dir),
                "journey_category": "drafts",
                "vault_scope": "private",
                "vault_root": "runtime-staging",
                "source_root": "runtime-staging",
                "promotion_state": "staged-leftover",
                "format": "directory",
                "skill_count": str(len(skill_paths)),
                "size_bytes": str(size_bytes),
                "size": _format_size(size_bytes),
                "clients": ",".join(clients),
                "staged_at": staged_at,
                "indexed_at": staged_at,
            }
        )
    return entries


def _sweep_docs_manifest_signature(documents_dir: Path) -> tuple[tuple[str, int], ...]:
    documents_root = Path(documents_dir).expanduser()
    if not documents_root.is_dir():
        return ()

    files: list[tuple[str, int]] = []
    try:
        candidates = documents_root.rglob("_manifest.jsonl")
        for path in candidates:
            try:
                if path.parent.name != ".archive" or path.is_symlink() or not path.is_file():
                    continue
            except OSError:
                continue
            files.append((_path_identity(path), _path_mtime_ns(path)))
    except OSError:
        return tuple(files)
    return tuple(sorted(files))


def _sweep_ledger_file_signature(root: Path) -> tuple[tuple[str, int], ...]:
    ledger_root = Path(root).expanduser()
    try:
        if ledger_root.is_symlink():
            return ()
        if ledger_root.is_file():
            if ledger_root.name == "sweep-ledger.jsonl" or (
                ledger_root.name == "sweep.jsonl" and ledger_root.parent.name == "_ledger"
            ):
                return ((_path_identity(ledger_root), _path_mtime_ns(ledger_root)),)
            return ()
        if not ledger_root.is_dir():
            return ()
    except OSError:
        return ()

    files: list[tuple[str, int]] = []
    try:
        candidates = list(ledger_root.rglob("sweep-ledger.jsonl"))
        new_ledger = ledger_root / "_ledger" / "sweep.jsonl"
        if new_ledger.is_file():
            candidates.append(new_ledger)
        for path in candidates:
            try:
                if path.is_symlink() or _has_symlink_between(ledger_root, path) or not path.is_file():
                    continue
            except OSError:
                continue
            files.append((_path_identity(path), _path_mtime_ns(path)))
    except OSError:
        return tuple(files)
    return tuple(sorted(files))


def _sweep_ledger_root_cache_signature(
    root: Path,
) -> tuple[str, int, tuple[tuple[str, int], ...]]:
    ledger_root = Path(root).expanduser()
    try:
        if ledger_root.is_symlink():
            return (
                _path_lexical_identity(ledger_root),
                _path_lstat_mtime_ns(ledger_root),
                (),
            )
    except OSError:
        return (_path_lexical_identity(ledger_root), 0, ())
    return (
        _path_identity(ledger_root),
        _path_mtime_ns(ledger_root),
        _sweep_ledger_file_signature(ledger_root),
    )


def _sweep_archive_cache_signature(
    module_path: Path,
    documents_dir: Path,
    ledger_roots: list[Path],
) -> tuple[object, ...]:
    return (
        _path_identity(module_path),
        _path_mtime_ns(module_path),
        _path_identity(documents_dir),
        _path_mtime_ns(documents_dir),
        _sweep_docs_manifest_signature(documents_dir),
        tuple(_sweep_ledger_root_cache_signature(root) for root in ledger_roots),
    )


def _sweep_archive_warning_entry(result: dict) -> dict | None:
    warnings = result.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
    try:
        warning_count = int(result.get("warning_count", len(warnings)) or 0)
    except (TypeError, ValueError):
        warning_count = len(warnings)
    if warning_count <= 0:
        return None

    warning_kinds = sorted(
        {str(warning.get("kind") or "warning") for warning in warnings if isinstance(warning, dict)}
    )[:8]
    warning_fields = sorted(
        {str(warning.get("field") or "") for warning in warnings if isinstance(warning, dict) and warning.get("field")}
    )[:8]

    return {
        "id": "sweep:archive-status:warnings",
        "type": "vault",
        "name": "Sweep archive warnings",
        "title": "Sweep archive warnings",
        "description": (f"Sweep archive skipped {warning_count} malformed or unsafe archive " "record(s)."),
        "hub": "system",
        "source_path": "",
        "journey_category": "archive",
        "archive_source": "sweep",
        "archive_mode": "status",
        "status": "warning",
        "warning_count": str(warning_count),
        "warning_kinds": ",".join(warning_kinds),
        "warning_fields": ",".join(warning_fields),
        "recovery_hint": "Review Sweep archive manifests and ledgers.",
    }


def _load_sweep_archive_entries(
    *,
    module_path: Path,
    documents_dir: Path,
    ledger_roots: list[Path],
) -> list[dict]:
    try:
        import sys
        import types

        source_path = _path_identity(module_path)
        source_mtime = _path_mtime_ns(module_path)
        module = sys.modules.get(_SWEEP_ARCHIVE_MODULE_NAME)
        if module is not None and (
            getattr(module, _SWEEP_ARCHIVE_MODULE_PATH_ATTR, None) != source_path
            or getattr(module, _SWEEP_ARCHIVE_MODULE_MTIME_ATTR, None) != source_mtime
        ):
            module = None
        if module is None:
            sys.modules.pop(_SWEEP_ARCHIVE_MODULE_NAME, None)
            source_text = module_path.read_text(encoding="utf-8")
            code = compile(source_text, source_path, "exec")
            module = types.ModuleType(_SWEEP_ARCHIVE_MODULE_NAME)
            module.__file__ = source_path
            module.__package__ = ""
            sys.modules[_SWEEP_ARCHIVE_MODULE_NAME] = module
            try:
                exec(code, module.__dict__)
            except Exception:
                if sys.modules.get(_SWEEP_ARCHIVE_MODULE_NAME) is module:
                    sys.modules.pop(_SWEEP_ARCHIVE_MODULE_NAME, None)
                raise
            setattr(module, _SWEEP_ARCHIVE_MODULE_PATH_ATTR, source_path)
            setattr(module, _SWEEP_ARCHIVE_MODULE_MTIME_ATTR, source_mtime)
        result = module.collect_sweep_archive_entries(
            documents_dir=documents_dir,
            ledger_roots=ledger_roots,
        )
        entries = result.get("entries", [])
        if not isinstance(entries, list):
            entries = []
        warning_entry = _sweep_archive_warning_entry(result)
        if warning_entry is not None:
            return [*entries, warning_entry]
        return entries
    except Exception:
        return []


def _sweep_archive_entries() -> list[dict]:
    global _sweep_archive_cache_entries, _sweep_archive_cache_key, _sweep_archive_cache_ts

    project_root = get_project_root()
    module_path = get_project_brain_skills_dir(project_root) / "routine-vault" / "scripts" / "archive_index.py"
    documents_dir = get_documents_dir()
    ledger_roots = [
        project_root / "archive",
        get_vault_dir() / "archive",
    ]
    cache_key = _sweep_archive_cache_signature(module_path, documents_dir, ledger_roots)
    now = _time.time()
    with _sweep_archive_cache_lock:
        if _sweep_archive_cache_key == cache_key and now - _sweep_archive_cache_ts < _SWEEP_ARCHIVE_CACHE_TTL:
            return list(_sweep_archive_cache_entries)

    entries = _load_sweep_archive_entries(
        module_path=module_path,
        documents_dir=documents_dir,
        ledger_roots=ledger_roots,
    )
    with _sweep_archive_cache_lock:
        _sweep_archive_cache_key = cache_key
        _sweep_archive_cache_entries = list(entries)
        _sweep_archive_cache_ts = now
    return entries
