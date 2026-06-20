"""Runtime state engine for the Browse active brain folder context."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.config.paths import get_runtime_dir
from src.lib.brain_discovery import build_discovery_snapshot


@dataclass(frozen=True)
class ActiveBrainFolderContext:
    scope: str
    label: str
    brain_id: str | None = None
    root: str | None = None
    project_root: str | None = None


@dataclass(frozen=True)
class ActiveBrainFolderContextResult:
    success: bool
    context: ActiveBrainFolderContext
    options: list[dict[str, Any]]
    repaired: bool = False
    error: str | None = None


@dataclass(frozen=True)
class _PersistedState:
    raw: dict[str, Any] | None
    invalid: bool = False


def default_active_context_path() -> Path:
    return get_runtime_dir() / "browse" / "active-folder-context.json"


def get_active_brain_folder_context(
    *,
    cwd: Path,
    project_root: Path | None = None,
    registry_path: Path | None = None,
    state_path: Path | None = None,
) -> ActiveBrainFolderContextResult:
    snapshot = build_discovery_snapshot(
        cwd=cwd,
        registry_path=registry_path,
        project_root=project_root,
        include_git_status=False,
    )
    options = build_folder_context_options(snapshot)
    path = state_path or default_active_context_path()
    persisted = _read_state(path)
    repaired = False

    if persisted.raw is None:
        context = _context_from_option(_all_option(options))
        repaired = persisted.invalid
    else:
        context = _validated_context(persisted.raw, options)
        if context is None:
            context = _context_from_option(_all_option(options))
            repaired = True

    _write_state(path, context)
    return ActiveBrainFolderContextResult(
        success=True,
        context=context,
        options=options,
        repaired=repaired,
    )


def set_active_brain_folder_context(
    requested: dict[str, Any],
    *,
    cwd: Path,
    project_root: Path | None = None,
    registry_path: Path | None = None,
    state_path: Path | None = None,
) -> ActiveBrainFolderContextResult:
    snapshot = build_discovery_snapshot(
        cwd=cwd,
        registry_path=registry_path,
        project_root=project_root,
        include_git_status=False,
    )
    options = build_folder_context_options(snapshot)
    path = state_path or default_active_context_path()
    context = _validated_context(requested, options)
    if context is None:
        persisted = _read_state(path)
        current = _validated_context(persisted.raw or {}, options)
        repaired = False
        if current is None:
            current = _context_from_option(_all_option(options))
            _write_state(path, current)
            repaired = persisted.invalid or persisted.raw is not None
        return ActiveBrainFolderContextResult(
            success=False,
            context=current,
            options=options,
            repaired=repaired,
            error="unknown_brain",
        )

    _write_state(path, context)
    return ActiveBrainFolderContextResult(
        success=True,
        context=context,
        options=options,
    )


def build_folder_context_options(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    detected_by_id = {
        detected["id"]: detected for detected in snapshot.get("detected_project_brains", []) if detected.get("id")
    }
    options: list[dict[str, Any]] = [
        {
            "id": "all",
            "scope": "all",
            "label": "All Brains",
            "state": "available",
        },
        {
            "id": "unassigned",
            "scope": "unassigned",
            "label": "Unassigned",
            "state": "available",
            "badge": "Repair",
        },
    ]

    registered_ids: set[str] = set()
    for brain in snapshot.get("brains", []):
        brain_id = brain.get("id")
        brain_type = brain.get("type")
        if not brain_id or brain_type not in {"personal", "project"}:
            continue
        registered_ids.add(brain_id)
        option = _registered_brain_option(brain)
        detected = detected_by_id.get(brain_id)
        if (
            brain_type == "project"
            and detected is not None
            and not _same_path(option.get("root"), detected.get("root"))
        ):
            option["state"] = "repairable"
            option["registered_root"] = option["root"]
            option["root"] = detected.get("root")
            option["project_root"] = detected.get("attached_project")
        options.append(option)

    for detected in snapshot.get("detected_project_brains", []):
        brain_id = detected.get("id")
        if not brain_id or brain_id in registered_ids:
            continue
        options.append(_detected_project_option(detected))

    return options


def _registered_brain_option(brain: dict[str, Any]) -> dict[str, Any]:
    brain_type = brain["type"]
    git = brain.get("git") or {}
    return {
        "id": f"brain:{brain['id']}",
        "scope": "brain",
        "brain_id": brain["id"],
        "type": brain_type,
        "label": _label_for_brain(brain["id"], brain_type, brain.get("description")),
        "root": brain.get("root"),
        "project_root": git.get("host_repo") if brain_type == "project" else None,
        "state": "available" if brain.get("exists") else "missing",
        "registered": True,
    }


def _detected_project_option(detected: dict[str, Any]) -> dict[str, Any]:
    brain_id = detected["id"]
    return {
        "id": f"detected:{brain_id}",
        "scope": "detected",
        "brain_id": brain_id,
        "type": "project",
        "label": _label_for_brain(brain_id, "project", detected.get("description")),
        "root": detected.get("root"),
        "project_root": detected.get("attached_project"),
        "state": "unregistered",
        "registered": False,
    }


def _validated_context(
    raw: dict[str, Any],
    options: list[dict[str, Any]],
) -> ActiveBrainFolderContext | None:
    scope = raw.get("scope")
    if scope == "all":
        return _context_from_option(_all_option(options))
    if scope == "unassigned":
        return _context_from_option(_unassigned_option(options))
    if scope != "brain":
        return None

    brain_id = raw.get("brain_id")
    if not isinstance(brain_id, str) or not brain_id:
        return None
    option = next(
        (option for option in options if option.get("scope") == "brain" and option.get("brain_id") == brain_id),
        None,
    )
    if option is None:
        return None
    if option.get("state") not in {"available", "repairable"}:
        return None
    return _context_from_option(option)


def _context_from_option(option: dict[str, Any]) -> ActiveBrainFolderContext:
    return ActiveBrainFolderContext(
        scope=option["scope"],
        label=option["label"],
        brain_id=option.get("brain_id"),
        root=option.get("root"),
        project_root=option.get("project_root"),
    )


def _all_option(options: list[dict[str, Any]]) -> dict[str, Any]:
    return next(option for option in options if option["id"] == "all")


def _unassigned_option(options: list[dict[str, Any]]) -> dict[str, Any]:
    return next(option for option in options if option["id"] == "unassigned")


def _read_state(path: Path) -> _PersistedState:
    if not path.is_file():
        return _PersistedState(raw=None)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _PersistedState(raw=None, invalid=True)
    if not isinstance(raw, dict):
        return _PersistedState(raw=None, invalid=True)
    return _PersistedState(raw=raw)


def _write_state(path: Path, context: ActiveBrainFolderContext) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(context), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _label_for_brain(brain_id: str, brain_type: str, description: str | None) -> str:
    if brain_type == "personal":
        return "Personal"
    if description:
        label = description.strip()
        lower = label.lower()
        for suffix in (" project brain", " brain"):
            if lower.endswith(suffix):
                label = label[: -len(suffix)].strip()
                break
        if label:
            return label
    return _label_from_id(brain_id)


def _label_from_id(brain_id: str) -> str:
    for prefix in ("project-", "personal-", "brain-"):
        if brain_id.startswith(prefix):
            brain_id = brain_id[len(prefix) :]
            break
    return brain_id.replace("_", " ").replace("-", " ").title()


def _same_path(left: object, right: object) -> bool:
    try:
        left_path = Path(str(left)).expanduser().resolve(strict=False)
        right_path = Path(str(right)).expanduser().resolve(strict=False)
        return left_path == right_path
    except OSError:
        return str(left) == str(right)
