"""hygiene_apply: atomic destructive primitive that moves stale-version
files into per-folder .archive/ directories.

Dry-run by default through the caller; `dry_run=False` enables actual
moves. Every move is validated independently — refusal of one move
does not abort others. Atomicity is per-file via os.rename.
"""
from __future__ import annotations


# TODO_CLEANUP: This file is 1109 lines — consider splitting into smaller modules
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

# Sibling loader for never_touch — uses a distinct spec name from hygiene_scan's
# loader so both modules can coexist in sys.modules within the same process.
_NEVER_TOUCH_PATH = _AugurPath(__file__).resolve().parent / "never_touch.py"
_nt_spec = _augur_importlib_util.spec_from_file_location("loop_hygiene_apply_never_touch", _NEVER_TOUCH_PATH)
if _nt_spec is None or _nt_spec.loader is None:
    raise RuntimeError(f"Unable to load never_touch from {_NEVER_TOUCH_PATH}")
_nt_mod = _augur_importlib_util.module_from_spec(_nt_spec)
_augur_sys.modules["loop_hygiene_apply_never_touch"] = _nt_mod
_nt_spec.loader.exec_module(_nt_mod)
is_never_touch = _nt_mod.is_never_touch

# Sibling loader for lifecycle_config — mirrors the never_touch pattern above.
_LIFECYCLE_PATH = _AugurPath(__file__).resolve().parent / "lifecycle_config.py"
_lc_spec = _augur_importlib_util.spec_from_file_location("loop_hygiene_apply_lifecycle_config", _LIFECYCLE_PATH)
if _lc_spec is None or _lc_spec.loader is None:
    raise RuntimeError(f"Unable to load lifecycle_config from {_LIFECYCLE_PATH}")
_lc_mod = _augur_importlib_util.module_from_spec(_lc_spec)
_augur_sys.modules["loop_hygiene_apply_lifecycle_config"] = _lc_mod
_lc_spec.loader.exec_module(_lc_mod)
LifecycleConfigError = _lc_mod.LifecycleConfigError
read_lifecycle_config = _lc_mod.read_lifecycle_config
read_milestones = _lc_mod.read_milestones

# Sibling loader for lifecycle_writer — keeps importlib-based tests package-free.
_LIFECYCLE_WRITER_PATH = _AugurPath(__file__).resolve().parent / "lifecycle_writer.py"
_lw_spec = _augur_importlib_util.spec_from_file_location(
    "loop_hygiene_apply_lifecycle_writer", _LIFECYCLE_WRITER_PATH
)
if _lw_spec is None or _lw_spec.loader is None:
    raise RuntimeError(f"Unable to load lifecycle_writer from {_LIFECYCLE_WRITER_PATH}")
_lw_mod = _augur_importlib_util.module_from_spec(_lw_spec)
_augur_sys.modules["loop_hygiene_apply_lifecycle_writer"] = _lw_mod
_lw_spec.loader.exec_module(_lw_mod)
append_known_group = _lw_mod.append_known_group
LifecycleWriterCollision = _lw_mod.LifecycleWriterCollision
LifecycleWriterError = _lw_mod.LifecycleWriterError

# Sibling loader for sweep_selection — keeps selection reads package-free.
_SELECTION_PATH = _AugurPath(__file__).resolve().parent / "sweep_selection.py"
_ss_spec = _augur_importlib_util.spec_from_file_location(
    "loop_hygiene_apply_sweep_selection",
    _SELECTION_PATH,
)
if _ss_spec is None or _ss_spec.loader is None:
    raise RuntimeError(f"Unable to load sweep_selection from {_SELECTION_PATH}")
_ss_mod = _augur_importlib_util.module_from_spec(_ss_spec)
_augur_sys.modules["loop_hygiene_apply_sweep_selection"] = _ss_mod
_ss_spec.loader.exec_module(_ss_mod)
read_selection = _ss_mod.read_selection

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_documents_dir, get_project_root, get_vault_dir

SUPPORTED_ROOTS = {"docs"}
DOCS_ARCHIVE_MODES = {"docs-archive", "docs-folder-archive"}
GIT_ARCHIVE_MODES = {"git-aware", "git-aware-archive"}
ARCHIVE_MODE_ALIASES = {
    "docs-folder-archive": "docs-archive",
    "git-aware-archive": "git-aware",
}
_GIT_ARCHIVE_MODULE = None


class HygieneApplyError(ValueError):
    """Raised when apply input is structurally invalid (unsupported root, etc.)."""


def hygiene_apply_selection(
    selection_id: str | dict[str, Any] | None = None,
    moves: list[dict[str, Any]] | None = None,
    *,
    selection: str | dict[str, Any] | None = None,
    dry_run: bool = True,
    apply_run_id: str | None = None,
) -> dict[str, Any]:
    """Apply archive decisions for targets captured in a typed selection."""
    selection_payload = _read_selection_payload(_selection_argument(selection_id, selection))
    move_requests = moves or []
    resolved_apply_run_id = apply_run_id or uuid.uuid4().hex
    move_results: list[dict[str, Any] | None] = [None] * len(move_requests)
    archive_records: list[dict[str, Any]] = []
    selected, invalid_selected = _build_selected_target_lookups(
        selection_payload.get("targets", []),
        selection_payload,
        dry_run=dry_run,
    )
    docs_batch: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    git_batch: list[tuple[int, dict[str, Any], dict[str, Any]]] = []

    for index, move in enumerate(move_requests):
        if not isinstance(move, dict):
            move_results[index] = _selection_apply_refusal(
                move={},
                dry_run=dry_run,
                refusal_category="malformed_move",
            )
            continue

        target, refusal = _resolve_selected_target(
            move,
            selected,
            invalid_selected,
            dry_run=dry_run,
        )
        if refusal is not None:
            move_results[index] = refusal
            continue

        assert target is not None
        mismatch = _move_target_mismatch(move, target, dry_run=dry_run)
        if mismatch is not None:
            move_results[index] = mismatch
            continue

        archive_mode = str(target.get("archive_mode") or "")
        if archive_mode in DOCS_ARCHIVE_MODES:
            docs_batch.append((index, target, move))
        elif archive_mode in GIT_ARCHIVE_MODES:
            git_batch.append((index, target, move))
        else:
            move_results[index] = _selection_apply_refusal(
                move=move,
                dry_run=dry_run,
                refusal_category="unsupported_archive_mode",
                target=target,
                extra={"archive_mode": archive_mode},
            )

    if docs_batch:
        docs_moves = [
            {
                "from": str(target.get("relative_path") or ""),
                "reason": str(move.get("reason") or ""),
                "artifact_group": _move_artifact_group(move, target),
            }
            for _index, target, move in docs_batch
        ]
        docs_result = hygiene_apply(
            root="docs",
            moves=docs_moves,
            dry_run=dry_run,
            apply_run_id=resolved_apply_run_id,
        )
        for (index, target, move), result in zip(docs_batch, docs_result["moves"], strict=True):
            enriched = _enrich_docs_selection_result(
                selection=selection_payload,
                target=target,
                move=move,
                result=result,
            )
            move_results[index] = enriched
            if enriched.get("status") == "succeeded":
                archive_records.append(
                    _docs_archive_record(
                        selection=selection_payload,
                        target=target,
                        move=move,
                        result=enriched,
                        apply_run_id=resolved_apply_run_id,
                    )
                )

    for index, target, move in git_batch:
        if dry_run:
            result = _dry_run_git_archive(
                target=target,
                move=move,
                apply_run_id=resolved_apply_run_id,
            )
        else:
            apply_git_history_purge_archive = _load_apply_git_history_purge_archive()
            result = apply_git_history_purge_archive(
                repo_root=Path(str(target.get("repository_root") or "")),
                source_path=Path(str(target.get("source_path") or target.get("absolute_path") or "")),
                source_tab=str(target.get("source_tab") or selection_payload.get("source_tab") or ""),
                source_kind=str(target.get("kind") or target.get("source_kind") or target.get("source_tab") or ""),
                reason=str(move.get("reason") or ""),
                artifact_group=_move_artifact_group(move, target),
                apply_run_id=resolved_apply_run_id,
                brain_id=str(target.get("brain_id") or target.get("target_repository_id") or "default"),
            )
        result["source_id"] = target.get("source_id")
        result["archive_mode"] = result.get("archive_mode") or target.get("archive_mode")
        result["kind"] = target.get("kind")
        result["selection_id"] = selection_payload.get("selection_id")
        if result.get("status") == "partial":
            result["status"] = "needs_attention"
        move_results[index] = result
        if result.get("status") == "succeeded":
            archive_records.append(
                _git_archive_record(
                    selection=selection_payload,
                    target=target,
                    result=result,
                    apply_run_id=resolved_apply_run_id,
                )
            )

    return {
        "dry_run": dry_run,
        "selection_id": selection_payload.get("selection_id"),
        "apply_run_id": resolved_apply_run_id,
        "moves": [result for result in move_results if result is not None],
        "archive_records": archive_records,
    }


def _selection_argument(
    selection_id: str | dict[str, Any] | None,
    selection: str | dict[str, Any] | None,
) -> str | dict[str, Any]:
    if selection is not None:
        if selection_id is not None:
            raise HygieneApplyError("pass either selection_id or selection, not both")
        return selection
    if selection_id is None:
        raise HygieneApplyError("selection_id or selection is required")
    return selection_id


def _read_selection_payload(selection_id: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(selection_id, dict):
        return selection_id
    return read_selection(str(selection_id))


def _build_selected_target_lookups(
    targets: Any,
    selection: dict[str, Any],
    *,
    dry_run: bool,
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    valid_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    invalid_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    if not isinstance(targets, list):
        return valid_lookup, invalid_lookup
    for raw_target in targets:
        if not isinstance(raw_target, dict):
            continue
        target, validation_refusal = _validated_selection_target(
            raw_target,
            selection,
            dry_run=dry_run,
        )
        lookup_target = target if validation_refusal is None else validation_refusal
        lookup = valid_lookup if validation_refusal is None else invalid_lookup
        assert lookup_target is not None
        for key in _target_lookup_keys(raw_target) + _target_lookup_keys(lookup_target):
            lookup.setdefault(key, lookup_target)
    return valid_lookup, invalid_lookup


def _target_lookup_keys(target: dict[str, Any]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    source_id = target.get("source_id")
    if source_id:
        keys.append(("source_id", str(source_id)))
    relative_path = target.get("relative_path")
    if relative_path:
        keys.append(("relative_path", str(relative_path)))
    for field in ("source_path", "absolute_path"):
        value = target.get(field)
        if value:
            try:
                keys.append(("absolute_path", str(Path(str(value)).resolve())))
            except OSError:
                keys.append(("absolute_path", str(value)))
    return keys


def _validated_selection_target(
    raw_target: dict[str, Any],
    selection: dict[str, Any],
    *,
    dry_run: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_tab = str(raw_target.get("source_tab") or selection.get("source_tab") or "")
    if source_tab not in _ss_mod.VALID_SOURCE_TABS:
        return None, _selection_validation_refusal(
            raw_target,
            {
                "source_id": str(raw_target.get("source_id") or ""),
                "source_path": str(raw_target.get("source_path") or ""),
                "refusal_category": "invalid_source_tab",
            },
            dry_run=dry_run,
            move=None,
        )

    _sync_selection_validation_roots()
    validation_target = dict(raw_target)
    original_archive_mode = str(raw_target.get("archive_mode") or "")
    validation_target["archive_mode"] = _canonical_archive_mode(original_archive_mode)
    validated, refusal = _ss_mod._validate_target(validation_target, source_tab)
    if refusal is not None:
        return None, _selection_validation_refusal(
            raw_target,
            refusal,
            dry_run=dry_run,
            move=None,
        )
    if validated is None:
        return None, _selection_validation_refusal(
            raw_target,
            {
                "source_id": str(raw_target.get("source_id") or ""),
                "source_path": str(raw_target.get("source_path") or ""),
                "refusal_category": "invalid_target",
            },
            dry_run=dry_run,
            move=None,
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
    *,
    dry_run: bool,
    move: dict[str, Any] | None,
) -> dict[str, Any]:
    result: dict[str, Any] = dict(refusal)
    result["status"] = _refusal_status(dry_run)
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
    if move is not None:
        _add_move_context(result, move)
    return result


def _resolve_selected_target(
    move: dict[str, Any],
    selected: dict[tuple[str, str], dict[str, Any]],
    invalid_selected: dict[tuple[str, str], dict[str, Any]],
    *,
    dry_run: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_id = move.get("source_id")
    if source_id is not None:
        key = ("source_id", str(source_id))
        invalid = invalid_selected.get(key)
        if invalid is not None:
            return None, _invalid_target_refusal(invalid, move)
        target = selected.get(key)
        if target is not None:
            return target, None
        return None, _selection_apply_refusal(
            move=move,
            dry_run=dry_run,
            refusal_category="unknown_target",
            extra={"source_id": str(source_id)},
        )

    for field in ("from", "relative_path"):
        value = move.get(field)
        if value is None:
            continue
        key = ("relative_path", str(value))
        invalid = invalid_selected.get(key)
        if invalid is not None:
            return None, _invalid_target_refusal(invalid, move)
        target = selected.get(key)
        if target is not None:
            return target, None
        return None, _selection_apply_refusal(
            move=move,
            dry_run=dry_run,
            refusal_category="unknown_target",
            extra={field: str(value)},
        )

    for field in ("source_path", "absolute_path"):
        value = move.get(field)
        if value is None:
            continue
        try:
            normalized = str(Path(str(value)).resolve())
        except OSError:
            normalized = str(value)
        key = ("absolute_path", normalized)
        invalid = invalid_selected.get(key)
        if invalid is not None:
            return None, _invalid_target_refusal(invalid, move)
        target = selected.get(key)
        if target is not None:
            return target, None
        return None, _selection_apply_refusal(
            move=move,
            dry_run=dry_run,
            refusal_category="unknown_target",
            extra={field: str(value)},
        )

    return None, _selection_apply_refusal(
        move=move,
        dry_run=dry_run,
        refusal_category="missing_target",
    )


def _invalid_target_refusal(invalid: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
    result = dict(invalid)
    _add_move_context(result, move)
    return result


def _move_target_mismatch(
    move: dict[str, Any],
    target: dict[str, Any],
    *,
    dry_run: bool,
) -> dict[str, Any] | None:
    expected_relative = str(target.get("relative_path") or "")
    for field in ("from", "relative_path"):
        value = move.get(field)
        if value is not None and str(value) != expected_relative:
            return _selection_apply_refusal(
                move=move,
                dry_run=dry_run,
                refusal_category="target_mismatch",
                target=target,
                extra={
                    "expected_relative_path": expected_relative,
                    "received_relative_path": str(value),
                },
            )

    expected_absolute = target.get("source_path") or target.get("absolute_path")
    if expected_absolute:
        try:
            expected_absolute_text = str(Path(str(expected_absolute)).resolve())
        except OSError:
            expected_absolute_text = str(expected_absolute)
        for field in ("source_path", "absolute_path"):
            value = move.get(field)
            if value is None:
                continue
            try:
                received_absolute_text = str(Path(str(value)).resolve())
            except OSError:
                received_absolute_text = str(value)
            if received_absolute_text != expected_absolute_text:
                return _selection_apply_refusal(
                    move=move,
                    dry_run=dry_run,
                    refusal_category="target_mismatch",
                    target=target,
                    extra={
                        "expected_absolute_path": expected_absolute_text,
                        "received_absolute_path": received_absolute_text,
                    },
                )
    return None


def _selection_apply_refusal(
    *,
    move: dict[str, Any],
    dry_run: bool,
    refusal_category: str,
    target: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": _refusal_status(dry_run),
        "refusal_category": refusal_category,
    }
    if target is not None:
        if target.get("source_id") is not None:
            result["source_id"] = target.get("source_id")
        if target.get("archive_mode") is not None:
            result["archive_mode"] = target.get("archive_mode")
        if target.get("kind") is not None:
            result["kind"] = target.get("kind")
    if extra:
        result.update(extra)
    _add_move_context(result, move)
    return result


def _add_move_context(result: dict[str, Any], move: dict[str, Any]) -> None:
    reason = move.get("reason")
    if reason is not None:
        result["reason"] = str(reason)
    source_id = move.get("source_id")
    if source_id is not None and "source_id" not in result:
        result["source_id"] = str(source_id)


def _refusal_status(dry_run: bool) -> str:
    return "would_refuse" if dry_run else "refused"


def _canonical_archive_mode(archive_mode: str) -> str:
    return ARCHIVE_MODE_ALIASES.get(archive_mode, archive_mode)


def _sync_selection_validation_roots() -> None:
    _ss_mod.get_documents_dir = get_documents_dir
    _ss_mod.get_project_root = get_project_root
    _ss_mod.get_vault_dir = get_vault_dir


def _load_git_archive_module():
    global _GIT_ARCHIVE_MODULE
    if _GIT_ARCHIVE_MODULE is not None:
        return _GIT_ARCHIVE_MODULE
    git_archive_path = _AugurPath(__file__).resolve().parent / "git_archive.py"
    spec = _augur_importlib_util.spec_from_file_location(
        "loop_hygiene_apply_git_archive",
        git_archive_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load git_archive from {git_archive_path}")
    module = _augur_importlib_util.module_from_spec(spec)
    _augur_sys.modules["loop_hygiene_apply_git_archive"] = module
    spec.loader.exec_module(module)
    _GIT_ARCHIVE_MODULE = module
    return module


def _load_apply_git_history_purge_archive():
    return _load_git_archive_module().apply_git_history_purge_archive


def _load_preview_git_history_purge_archive():
    return _load_git_archive_module().preview_git_history_purge_archive


def _move_artifact_group(move: dict[str, Any], target: dict[str, Any]) -> str | None:
    value = move.get("artifact_group")
    if value is not None:
        return str(value)
    value = target.get("artifact_group")
    if value is not None:
        return str(value)
    metadata = target.get("metadata")
    if isinstance(metadata, dict) and metadata.get("artifact_group") is not None:
        return str(metadata["artifact_group"])
    return None


def _enrich_docs_selection_result(
    *,
    selection: dict[str, Any],
    target: dict[str, Any],
    move: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(result)
    enriched["selection_id"] = selection.get("selection_id")
    enriched["source_id"] = target.get("source_id")
    enriched["source_tab"] = target.get("source_tab") or selection.get("source_tab")
    enriched["kind"] = target.get("kind")
    enriched["archive_mode"] = target.get("archive_mode")
    enriched["absolute_path"] = str(Path(str(target.get("source_path") or "")).resolve())
    enriched["repository_root"] = target.get("repository_root")
    enriched["artifact_group"] = _move_artifact_group(move, target)
    return enriched


def _docs_archive_record(
    *,
    selection: dict[str, Any],
    target: dict[str, Any],
    move: dict[str, Any],
    result: dict[str, Any],
    apply_run_id: str,
) -> dict[str, Any]:
    return {
        "archive_source": "sweep",
        "selection_id": selection.get("selection_id"),
        "source_id": target.get("source_id"),
        "source_tab": target.get("source_tab") or selection.get("source_tab"),
        "kind": target.get("kind"),
        "archive_mode": target.get("archive_mode"),
        "original_path": str(Path(str(target.get("source_path") or "")).resolve()),
        "relative_path": target.get("relative_path"),
        "archived_path": result.get("to"),
        "repository_root": target.get("repository_root"),
        "git_action": None,
        "reason": result.get("reason", move.get("reason", "")),
        "artifact_group": _move_artifact_group(move, target),
        "apply_run_id": apply_run_id,
        "recovery_hint": None,
    }


def _git_archive_record(
    *,
    selection: dict[str, Any],
    target: dict[str, Any],
    result: dict[str, Any],
    apply_run_id: str,
) -> dict[str, Any]:
    return {
        "archive_source": "sweep",
        "selection_id": selection.get("selection_id"),
        "source_id": target.get("source_id"),
        "source_tab": target.get("source_tab") or selection.get("source_tab"),
        "kind": target.get("kind"),
        "archive_mode": result.get("archive_mode") or target.get("archive_mode"),
        "original_path": result.get("original_path"),
        "relative_path": target.get("relative_path"),
        "archived_path": result.get("archived_path"),
        "repository_root": result.get("repo_root"),
        "git_action": result.get("git_action"),
        "reason": result.get("reason", ""),
        "artifact_group": result.get("artifact_group"),
        "apply_run_id": apply_run_id,
        "recovery_hint": result.get("recovery_hint"),
        "ledger_path": result.get("ledger_path"),
        "archive_record_id": result.get("archive_record_id"),
        "archive_commit": result.get("archive_commit"),
        "archive_pushed": result.get("archive_pushed"),
        "purge_commit": result.get("purge_commit"),
        "purge_pushed": result.get("purge_pushed"),
        "purged": result.get("purged"),
        "brain_id": result.get("brain_id"),
        "source_kind": result.get("source_kind") or target.get("kind"),
    }


def _dry_run_git_archive(
    *,
    target: dict[str, Any],
    move: dict[str, Any],
    apply_run_id: str,
) -> dict[str, Any]:
    preview_git_history_purge_archive = _load_preview_git_history_purge_archive()
    return preview_git_history_purge_archive(
        repo_root=Path(str(target.get("repository_root") or "")),
        source_path=Path(str(target.get("source_path") or target.get("absolute_path") or "")),
        source_tab=str(target.get("source_tab") or ""),
        source_kind=str(target.get("kind") or target.get("source_kind") or target.get("source_tab") or ""),
        reason=str(move.get("reason") or ""),
        artifact_group=_move_artifact_group(move, target),
        apply_run_id=apply_run_id,
        brain_id=str(target.get("brain_id") or target.get("target_repository_id") or "default"),
    )


def hygiene_apply(
    root: str,
    moves: list[dict[str, Any]],
    dry_run: bool,
    lifecycle_updates: list[dict[str, Any]] | None = None,
    apply_run_id: str | None = None,
    store_root: Path | None = None,
) -> dict[str, Any]:
    """Apply (or dry-run) archive moves and optional lifecycle updates.

    Args:
        root: store identifier. MVP supports only "docs".
        moves: list of {from, reason, artifact_group} dicts. `from` is
            relative to the store root.
        dry_run: when True, validate every move without modifying disk.
        lifecycle_updates: optional {folder, known_group} entries to write
            before moves so approved cache decisions survive partial move failures.
        apply_run_id: optional caller-provided run id for manifest correlation.
        store_root: optional explicit docs store root. Defaults to configured
            documents dir so existing callers keep the same behavior.

    Returns:
        Dict with: dry_run, moves (list of per-move results),
        total_bytes_archived, paths_written, lifecycle_updates.
    """
    if root not in SUPPORTED_ROOTS:
        raise HygieneApplyError(
            f"unsupported root: {root!r}; MVP supports only {sorted(SUPPORTED_ROOTS)}"
        )

    store_root = (store_root or get_documents_dir()).resolve()
    lifecycle_results = _process_lifecycle_updates(lifecycle_updates or [], store_root, dry_run)
    move_results: list[dict[str, Any]] = []
    total_bytes = 0
    paths_written: list[str] = []
    resolved_apply_run_id = apply_run_id or uuid.uuid4().hex
    successful_archive_dirs: set[Path] = set()

    for move in moves:
        src_rel = move["from"]
        dest_rel = _compute_archive_destination(src_rel)
        result = {
            "from": src_rel,
            "to": dest_rel,
            "reason": move.get("reason", ""),
            "artifact_group": move.get("artifact_group"),
        }
        refusal, src_abs = _validate_move(src_rel, store_root)
        if refusal is not None:
            result["status"] = "would_refuse" if dry_run else "refused"
            result["refusal_category"] = refusal
        else:
            assert src_abs is not None
            dest_abs = _archive_destination_path(store_root, dest_rel)
            dest_refusal = _archive_destination_refusal(
                store_root=store_root,
                dest_abs=dest_abs,
                allow_existing_file=True,
            )
            if dest_refusal is not None:
                result["status"] = "would_refuse" if dry_run else "refused"
                result["refusal_category"] = dest_refusal
            elif dry_run:
                result["status"] = "would_succeed"
                result["size_bytes"] = src_abs.stat().st_size
            else:
                # Real apply
                try:
                    dest_abs.parent.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    result["status"] = "refused"
                    result["refusal_category"] = "archive_parent_create_failed"
                    result["error"] = str(exc)
                    move_results.append(result)
                    continue
                actual_dest = _resolve_destination(src_abs, dest_abs)
                actual_dest_refusal = _archive_destination_refusal(
                    store_root=store_root,
                    dest_abs=actual_dest,
                    allow_existing_file=False,
                )
                if actual_dest_refusal is not None:
                    result["status"] = "refused"
                    result["refusal_category"] = actual_dest_refusal
                    move_results.append(result)
                    continue
                # Refuse cross-filesystem
                if src_abs.stat().st_dev != dest_abs.parent.stat().st_dev:
                    result["status"] = "refused"
                    result["refusal_category"] = "cross_filesystem"
                    move_results.append(result)
                    continue
                size_bytes = src_abs.stat().st_size
                os.rename(src_abs, actual_dest)
                result["status"] = "succeeded"
                result["to"] = str(actual_dest.relative_to(store_root))
                result["size_bytes"] = size_bytes
                total_bytes += size_bytes
                paths_written.append(result["to"])

                # Write manifest; on failure, roll back the rename.
                entry = {
                    "archived_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "from": src_rel,
                    "to": result["to"],
                    "reason": result["reason"],
                    "artifact_group": result.get("artifact_group"),
                    "apply_run_id": resolved_apply_run_id,
                }
                try:
                    _append_manifest(actual_dest.parent, entry)
                except OSError as exc:
                    # Roll back the rename so disk state matches the failed result.
                    os.rename(actual_dest, src_abs)
                    result["status"] = "refused"
                    result["refusal_category"] = "manifest_write_failed"
                    result["error"] = str(exc)
                    # Undo total_bytes / paths_written accounting
                    total_bytes -= size_bytes
                    paths_written.pop()
                    move_results.append(result)
                    continue
                successful_archive_dirs.add(actual_dest.parent)
        move_results.append(result)

    if not dry_run and successful_archive_dirs:
        for archive_dir in successful_archive_dirs:
            written = _ensure_augur_ignore(archive_dir)
            if written is not None:
                paths_written.append(str(written.relative_to(store_root)))
        written = _ensure_gitignore_entry(store_root)
        if written is not None:
            paths_written.append(str(written.relative_to(store_root)))

    return {
        "dry_run": dry_run,
        "moves": move_results,
        "total_bytes_archived": total_bytes,
        "paths_written": paths_written,
        "lifecycle_updates": lifecycle_results,
    }


def _compute_archive_destination(src_rel: str) -> str:
    """Given a source relative to the store root, return the archive destination.

    e.g. 'websites/x.zip' -> 'websites/.archive/x.zip'
    """
    p = Path(src_rel)
    return str(p.parent / ".archive" / p.name)


def _archive_destination_path(store_root: Path, dest_rel: str) -> Path:
    return Path(os.path.abspath(store_root / dest_rel))


def _archive_destination_refusal(
    *,
    store_root: Path,
    dest_abs: Path,
    allow_existing_file: bool,
) -> str | None:
    try:
        dest_abs.relative_to(store_root)
    except ValueError:
        return "outside_store"

    parent_refusal = _archive_parent_refusal(store_root=store_root, parent=dest_abs.parent)
    if parent_refusal is not None:
        return parent_refusal

    if dest_abs.is_symlink():
        return "archive_destination_symlink"
    if dest_abs.exists() and not allow_existing_file:
        return "archive_destination_exists"
    return None


def _archive_parent_refusal(*, store_root: Path, parent: Path) -> str | None:
    try:
        rel_parent = parent.relative_to(store_root)
    except ValueError:
        return "outside_store"

    current = store_root
    for part in rel_parent.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if current.is_symlink():
                return "archive_parent_symlink"
            if not current.is_dir():
                return "archive_parent_not_directory"
            continue
        break
    return None


def _append_manifest(archive_dir: Path, entry: dict[str, Any]) -> None:
    """Append a single JSON object as one line to _manifest.jsonl.

    Uses fsync to ensure the line hits disk before we trust the move.
    """
    manifest = archive_dir / "_manifest.jsonl"
    line = json.dumps(entry, separators=(",", ":")) + "\n"
    with manifest.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def _ensure_augur_ignore(archive_dir: Path) -> Path | None:
    """Create .augur-ignore at the archive root with default '*\\n' if absent.

    Returns the path if it was newly created; None if it already existed.
    """
    path = archive_dir / ".augur-ignore"
    if path.exists():
        return None
    path.write_text("*\n")
    return path


def _ensure_gitignore_entry(store_root: Path) -> Path | None:
    """Append '.archive/' to <store_root>/.gitignore if not already present.

    Returns the path if it was newly written/appended; None if no change.
    """
    gi = store_root / ".gitignore"
    existing_lines: list[str] = []
    if gi.exists():
        existing_lines = gi.read_text().splitlines()
        if ".archive/" in [ln.strip() for ln in existing_lines]:
            return None
    new_content = "\n".join(existing_lines + [".archive/"]) + "\n"
    gi.write_text(new_content)
    return gi


def _resolve_destination(src_abs: Path, dest_abs: Path) -> Path:
    """If dest_abs exists, append .dup-<shorthash-of-src-path> to break the tie.

    Hash uses the source path so re-archiving the same source path always
    collides to the same dup destination (idempotent).
    """
    if not dest_abs.exists():
        return dest_abs
    short_hash = hashlib.sha256(str(src_abs).encode()).hexdigest()[:8]
    return dest_abs.with_name(f"{dest_abs.name}.dup-{short_hash}")


def _validate_move(src_rel: str, store_root: Path) -> tuple[str | None, Path | None]:
    """Return (refusal_category, src_abs) — refusal_category is None if the move is OK."""
    src_rel_path = Path(src_rel)
    if is_never_touch(src_rel_path):
        return "never_touch", None

    # Outside-store: any move whose resolved absolute path escapes the store root.
    src_abs = (store_root / src_rel).resolve()
    try:
        src_abs.relative_to(store_root)
    except ValueError:
        return "outside_store", None

    # Use the un-resolved path for symlink detection so we don't follow the link.
    src_link_path = store_root / src_rel
    if not src_link_path.exists() and not src_link_path.is_symlink():
        return "source_missing", src_abs
    if src_link_path.is_symlink():
        return "symlink", src_abs
    if not src_link_path.is_file():
        return "source_missing", src_abs

    # Milestone check
    folder = src_abs.parent
    try:
        pins = read_milestones(folder)
    except LifecycleConfigError:
        pins = []
    for pin in pins:
        pin_abs = (store_root / pin.relative_path).resolve()
        if pin_abs == src_abs:
            return "milestone_pinned", src_abs

    # Deploy-root check
    try:
        cfg = read_lifecycle_config(folder)
    except LifecycleConfigError:
        cfg = None
    if cfg is not None and cfg.deploy_root:
        return "deploy_root", src_abs

    return None, src_abs


def _process_lifecycle_updates(
    updates: list[dict[str, Any]],
    store_root: Path,
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Validate and optionally append known_group entries before moves run."""
    results: list[dict[str, Any]] = []
    for update in updates:
        folder_rel = update.get("folder")
        entry = update.get("known_group")
        result: dict[str, Any] = {
            "folder": folder_rel,
            "known_group_name": entry.get("name") if isinstance(entry, dict) else None,
        }

        if not isinstance(folder_rel, str) or not isinstance(entry, dict):
            result["status"] = "refused" if not dry_run else "would_refuse"
            result["refusal_category"] = "malformed_update"
            results.append(result)
            continue

        malformed = _validate_known_group_entry(entry)
        if malformed is not None:
            result["status"] = "refused" if not dry_run else "would_refuse"
            result["refusal_category"] = "malformed_update"
            result["error"] = malformed
            results.append(result)
            continue

        folder_abs = (store_root / folder_rel).resolve()
        try:
            folder_abs.relative_to(store_root)
        except ValueError:
            result["status"] = "refused" if not dry_run else "would_refuse"
            result["refusal_category"] = "outside_store"
            results.append(result)
            continue
        if not folder_abs.is_dir():
            result["status"] = "refused" if not dry_run else "would_refuse"
            result["refusal_category"] = "folder_missing"
            results.append(result)
            continue

        if dry_run:
            collision_or_malformed = _dry_run_lifecycle_update_refusal(folder_abs, entry)
            if collision_or_malformed is not None:
                result["status"] = "would_refuse"
                result["refusal_category"] = collision_or_malformed
            else:
                result["status"] = "would_succeed"
            results.append(result)
            continue

        try:
            append_known_group(folder_abs, entry)
            result["status"] = "written"
        except LifecycleWriterCollision as exc:
            result["status"] = "refused"
            result["refusal_category"] = "lifecycle_collision"
            result["error"] = str(exc)
        except LifecycleWriterError as exc:
            result["status"] = "refused"
            result["refusal_category"] = "lifecycle_malformed"
            result["error"] = str(exc)
        results.append(result)
    return results


def _dry_run_lifecycle_update_refusal(folder_abs: Path, entry: dict[str, Any]) -> str | None:
    yaml_path = folder_abs / ".augur-lifecycle.yaml"
    if not yaml_path.exists():
        return None
    try:
        existing = yaml.safe_load(yaml_path.read_text()) or {}
    except yaml.YAMLError:
        return "lifecycle_malformed"
    if not isinstance(existing, dict):
        return "lifecycle_malformed"
    groups = existing.get("known_groups", [])
    if not isinstance(groups, list):
        return "lifecycle_malformed"
    for group in groups:
        if isinstance(group, dict) and group.get("name") == entry.get("name"):
            return "lifecycle_collision"
    return None


def _validate_known_group_entry(entry: dict[str, Any]) -> str | None:
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        return "known_group.name must be a non-empty string"
    strategy = entry.get("canonical_strategy")
    if strategy not in {"highest_version", "explicit", "not_a_group"}:
        return "known_group.canonical_strategy is invalid"
    if strategy == "highest_version":
        pattern = entry.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return "highest_version requires pattern"
    if strategy in {"explicit", "not_a_group"}:
        members = entry.get("members")
        if not isinstance(members, list) or not all(isinstance(member, str) for member in members):
            return f"{strategy} requires members"
    if strategy == "explicit":
        canonical = entry.get("canonical")
        if not isinstance(canonical, str) or not canonical:
            return "explicit requires canonical"
    return None
