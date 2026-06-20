"""hygiene_scan: read-only recursive scan of a folder under Documents.

Returns file listing, optional lifecycle config, milestone pins, and
skipped never-touch paths. No side effects. The classifier (the agent
in the user's session) consumes this output.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)

# Load sibling never_touch module via file-path loader so importlib-based
# test bootstrap (no package context) works the same as runtime.
_NEVER_TOUCH_PATH = _AugurPath(__file__).resolve().parent / "never_touch.py"
_nt_spec = _augur_importlib_util.spec_from_file_location("loop_hygiene_never_touch", _NEVER_TOUCH_PATH)
if _nt_spec is None or _nt_spec.loader is None:
    raise RuntimeError(f"Unable to load never_touch from {_NEVER_TOUCH_PATH}")
_nt_mod = _augur_importlib_util.module_from_spec(_nt_spec)
_augur_sys.modules["loop_hygiene_never_touch"] = _nt_mod
_nt_spec.loader.exec_module(_nt_mod)
is_never_touch = _nt_mod.is_never_touch

# Sibling loader for lifecycle_config — mirrors the never_touch pattern above.
_LIFECYCLE_PATH = _AugurPath(__file__).resolve().parent / "lifecycle_config.py"
_lc_spec = _augur_importlib_util.spec_from_file_location("loop_hygiene_lifecycle_config", _LIFECYCLE_PATH)
if _lc_spec is None or _lc_spec.loader is None:
    raise RuntimeError(f"Unable to load lifecycle_config from {_LIFECYCLE_PATH}")
_lc_mod = _augur_importlib_util.module_from_spec(_lc_spec)
_augur_sys.modules["loop_hygiene_lifecycle_config"] = _lc_mod
_lc_spec.loader.exec_module(_lc_mod)
LifecycleConfig = _lc_mod.LifecycleConfig
LifecycleConfigError = _lc_mod.LifecycleConfigError
MilestonePin = _lc_mod.MilestonePin
read_lifecycle_config = _lc_mod.read_lifecycle_config
read_milestones = _lc_mod.read_milestones

# Sibling loader for sweep_selection — keeps selection reads package-free.
_SELECTION_PATH = _AugurPath(__file__).resolve().parent / "sweep_selection.py"
_ss_spec = _augur_importlib_util.spec_from_file_location("loop_hygiene_sweep_selection", _SELECTION_PATH)
if _ss_spec is None or _ss_spec.loader is None:
    raise RuntimeError(f"Unable to load sweep_selection from {_SELECTION_PATH}")
_ss_mod = _augur_importlib_util.module_from_spec(_ss_spec)
_augur_sys.modules["loop_hygiene_sweep_selection"] = _ss_mod
_ss_spec.loader.exec_module(_ss_mod)
read_selection = _ss_mod.read_selection

import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.paths import get_documents_dir, get_project_root, get_vault_dir

ARCHIVE_MODE_ALIASES = {
    "docs-folder-archive": "docs-archive",
    "git-aware-archive": "git-aware",
}


class HygieneScanError(ValueError):
    """Raised when scan input is invalid (path outside Documents, missing, etc.)."""


def hygiene_scan_selection(selection_id: str | dict[str, Any]) -> dict[str, Any]:
    """Scan exactly the files captured in a typed Browse sweep selection.

    `selection_id` is the public entry point used by MCP callers. A dict is also
    accepted for importlib-heavy tests and future internal callers, but the path
    always treats the persisted selection as the source of truth.
    """
    selection = _read_selection_payload(selection_id)
    files: list[dict[str, Any]] = []
    warnings: list[str] = []
    validation_refusals: list[dict[str, Any]] = []
    raw_targets = selection.get("targets", [])
    if not isinstance(raw_targets, list):
        raw_targets = []
        validation_refusals.append(
            {
                "status": "refused",
                "refusal_category": "malformed_targets",
            }
        )
        warnings.append("selection targets malformed")

    for raw_target in raw_targets:
        target, validation_refusal = _validated_selection_target(raw_target, selection)
        if validation_refusal is not None:
            validation_refusals.append(validation_refusal)
            warnings.append(_selection_refusal_warning(validation_refusal))
            continue
        assert target is not None

        source = Path(str(target.get("source_path") or target.get("absolute_path") or ""))
        try:
            stat = source.stat()
            content_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        except OSError as exc:
            warnings.append(f"source unreadable: {target.get('source_id')} ({exc})")
            continue

        relative_path = str(target.get("relative_path") or "")
        mtime_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        item = {
            "selection_id": selection.get("selection_id"),
            "source_id": target.get("source_id"),
            "source_tab": target.get("source_tab") or selection.get("source_tab"),
            "kind": target.get("kind"),
            "name": source.name,
            "absolute_path": str(source.resolve()),
            "source_path": str(source.resolve()),
            "relative_path": relative_path,
            "folder_relative_path": str(Path(relative_path).parent),
            "repository_root": target.get("repository_root"),
            "archive_mode": target.get("archive_mode"),
            "artifact_group": _target_artifact_group(target),
            "root_key": target.get("root_key"),
            "title": target.get("title"),
            "size_bytes": stat.st_size,
            "mtime_iso": mtime_iso,
            "content_hash_sha256": content_hash,
            "metadata": target.get("metadata") or {},
        }
        files.append(item)

    return {
        "selection_id": selection.get("selection_id"),
        "source_tab": selection.get("source_tab"),
        "filter_summary": selection.get("filter_summary") or {},
        "target_count": len(raw_targets),
        "candidate_count": len(files),
        "files": files,
        "candidates": files,
        "refusals": _selection_refusals(selection) + validation_refusals,
        "warnings": warnings,
    }


def _read_selection_payload(selection_id: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(selection_id, dict):
        return selection_id
    return read_selection(str(selection_id))


def _selection_refusals(selection: dict[str, Any]) -> list[dict[str, Any]]:
    refusals = selection.get("refusals", [])
    if not isinstance(refusals, list):
        return []
    return [refusal for refusal in refusals if isinstance(refusal, dict)]


def _validated_selection_target(
    raw_target: Any,
    selection: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(raw_target, dict):
        return None, {
            "status": "refused",
            "refusal_category": "malformed_target",
        }

    source_tab = str(raw_target.get("source_tab") or selection.get("source_tab") or "")
    if source_tab not in _ss_mod.VALID_SOURCE_TABS:
        return None, _selection_validation_refusal(
            raw_target,
            {
                "source_id": str(raw_target.get("source_id") or ""),
                "source_path": str(raw_target.get("source_path") or ""),
                "refusal_category": "invalid_source_tab",
            },
        )

    _sync_selection_validation_roots()
    validation_target = dict(raw_target)
    original_archive_mode = str(raw_target.get("archive_mode") or "")
    validation_target["archive_mode"] = _canonical_archive_mode(original_archive_mode)
    validated, refusal = _ss_mod._validate_target(validation_target, source_tab)
    if refusal is not None:
        return None, _selection_validation_refusal(raw_target, refusal)
    if validated is None:
        return None, _selection_validation_refusal(
            raw_target,
            {
                "source_id": str(raw_target.get("source_id") or ""),
                "source_path": str(raw_target.get("source_path") or ""),
                "refusal_category": "invalid_target",
            },
        )

    target = dict(raw_target)
    target.update(
        {
            "kind": validated.kind,
            "source_path": validated.source_path,
            "absolute_path": validated.source_path,
            "source_id": validated.source_id,
            "archive_mode": original_archive_mode or validated.archive_mode,
            "source_tab": source_tab,
            "title": validated.title,
            "relative_path": validated.relative_path,
            "root_key": validated.root_key,
            "repository_root": validated.repository_root,
            "metadata": dict(validated.metadata),
        }
    )
    return target, None


def _selection_validation_refusal(
    raw_target: dict[str, Any],
    refusal: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = dict(refusal)
    result["status"] = "refused"
    source_id = raw_target.get("source_id")
    if source_id is not None:
        result["source_id"] = str(source_id)
    source_path = raw_target.get("source_path") or raw_target.get("absolute_path")
    if source_path is not None:
        result["source_path"] = str(source_path)
    archive_mode = raw_target.get("archive_mode")
    if archive_mode is not None:
        result["archive_mode"] = str(archive_mode)
    kind = raw_target.get("kind")
    if kind is not None:
        result["kind"] = str(kind)
    return result


def _selection_refusal_warning(refusal: dict[str, Any]) -> str:
    source_id = refusal.get("source_id") or "<unknown>"
    category = refusal.get("refusal_category") or "invalid_target"
    return f"selection target refused: {source_id} ({category})"


def _canonical_archive_mode(archive_mode: str) -> str:
    return ARCHIVE_MODE_ALIASES.get(archive_mode, archive_mode)


def _sync_selection_validation_roots() -> None:
    _ss_mod.get_documents_dir = get_documents_dir
    _ss_mod.get_project_root = get_project_root
    _ss_mod.get_vault_dir = get_vault_dir


def _target_artifact_group(target: dict[str, Any]) -> str | None:
    artifact_group = target.get("artifact_group")
    if artifact_group is not None:
        return str(artifact_group)
    metadata = target.get("metadata")
    if isinstance(metadata, dict) and metadata.get("artifact_group") is not None:
        return str(metadata["artifact_group"])
    return None


def hygiene_scan(path: str) -> dict[str, Any]:
    """Scan a folder under Documents.

    Args:
        path: absolute or relative path. Relative paths are resolved
        against the current working directory.

    Returns:
        Dict with keys: root, scanned_path, files, lifecycle_config,
        folder_lifecycle_configs, milestone_pins, folder_milestone_pins,
        never_touch_skipped, warnings.

    Raises:
        HygieneScanError: path is outside Documents, missing, or not a directory.
    """
    docs_root = get_documents_dir().resolve()
    candidate = Path(path).expanduser().resolve()

    if not candidate.exists():
        raise HygieneScanError(f"path does not exist: {candidate}")
    if not candidate.is_dir():
        raise HygieneScanError(f"path is not a directory: {candidate}")
    try:
        rel_scanned = candidate.relative_to(docs_root)
    except ValueError:
        raise HygieneScanError(f"path is outside Documents ({docs_root}): {candidate}") from None

    files: list[dict[str, Any]] = []
    never_touch_skipped: list[str] = []
    warnings: list[str] = []

    # Backward-compatible root-folder fields plus recursive per-folder maps.
    lifecycle_config: dict[str, Any] | None = None
    milestone_pins: list[dict[str, Any]] = []
    folder_lifecycle_configs: dict[str, dict[str, Any]] = {}
    folder_milestone_pins: dict[str, list[dict[str, Any]]] = {}

    def _folder_key(folder: Path) -> str:
        return str(folder.relative_to(docs_root))

    def _lifecycle_to_dict(cfg: LifecycleConfig) -> dict[str, Any]:
        data = asdict(cfg)
        data["known_groups"] = list(data.get("known_groups", []))
        for group in data["known_groups"]:
            if group.get("members") is not None:
                group["members"] = list(group["members"])
        return data

    def _record_folder_metadata(folder: Path) -> bool:
        """Read optional per-folder policy. Return False to skip this subtree."""
        nonlocal lifecycle_config, milestone_pins

        folder_key = _folder_key(folder)
        is_root_folder = folder == candidate

        try:
            cfg = read_lifecycle_config(folder)
            if cfg is not None:
                if not cfg.enabled:
                    message = f"lifecycle enabled: false at {folder} — refusing scan"
                    if is_root_folder:
                        raise HygieneScanError(message)
                    warnings.append(
                        f"lifecycle enabled: false at {folder_key} — skipped subtree"
                    )
                    return False
                cfg_dict = _lifecycle_to_dict(cfg)
                folder_lifecycle_configs[folder_key] = cfg_dict
                if is_root_folder:
                    lifecycle_config = cfg_dict
        except LifecycleConfigError as exc:
            warnings.append(f"lifecycle config parse error: {exc}")

        try:
            pins = read_milestones(folder)
            pin_dicts = [asdict(p) for p in pins]
            if pin_dicts:
                folder_milestone_pins[folder_key] = pin_dicts
            if is_root_folder:
                milestone_pins = pin_dicts
        except LifecycleConfigError as exc:
            warnings.append(f"milestones parse error: {exc}")

        return True

    def _scan_folder(folder: Path) -> None:
        if not _record_folder_metadata(folder):
            return

        for entry in sorted(folder.iterdir(), key=lambda p: p.name):
            rel_to_scanned = entry.relative_to(candidate)
            rel_text = str(rel_to_scanned)
            if is_never_touch(rel_to_scanned):
                never_touch_skipped.append(rel_text)
                continue
            if entry.is_symlink():
                warnings.append(f"refused symlink: {rel_text}")
                continue
            if entry.is_dir():
                _scan_folder(entry)
                continue
            if not entry.is_file():
                continue

            stat = entry.stat()
            mtime_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            content_hash = hashlib.sha256(entry.read_bytes()).hexdigest()
            files.append({
                "name": entry.name,
                "relative_path": str(entry.relative_to(docs_root)),
                "relative_to_scanned": rel_text,
                "folder_relative_path": str(entry.parent.relative_to(docs_root)),
                "size_bytes": stat.st_size,
                "mtime_iso": mtime_iso,
                "content_hash_sha256": content_hash,
                "is_symlink": False,
            })

    _scan_folder(candidate)

    return {
        "root": str(docs_root),
        "scanned_path": str(rel_scanned),
        "files": files,
        "lifecycle_config": lifecycle_config,
        "folder_lifecycle_configs": folder_lifecycle_configs,
        "milestone_pins": milestone_pins,
        "folder_milestone_pins": folder_milestone_pins,
        "never_touch_skipped": never_touch_skipped,
        "warnings": warnings,
    }
