"""Load and validate the setup-completeness item registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .types import ActionType, PhaseId


class RegistryError(ValueError):
    """Raised when setup-items.yaml is malformed."""


@dataclass(frozen=True)
class RegistryAction:
    type: ActionType
    label: str
    command: str | None = None
    route: str | None = None
    mcp_tool: str | None = None


@dataclass(frozen=True)
class RegistryItem:
    id: str
    label: str
    description: str
    probe: str
    action: RegistryAction


@dataclass(frozen=True)
class RegistryPhase:
    id: PhaseId
    label: str
    items: list[RegistryItem]


@dataclass(frozen=True)
class SetupRegistry:
    version: int
    phases: list[RegistryPhase]


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{field} must be a non-empty string")
    return value.strip()


def _parse_action(raw: object, item_id: str) -> RegistryAction:
    if not isinstance(raw, dict):
        raise RegistryError(f"{item_id}: action must be a mapping")
    action_type = _require_text(raw.get("type"), f"{item_id}.action.type")
    if action_type not in {"command", "route", "mcp"}:
        raise RegistryError(f"{item_id}: unsupported action type {action_type}")
    label = _require_text(raw.get("label"), f"{item_id}.action.label")
    command = raw.get("command")
    route = raw.get("route")
    mcp_tool = raw.get("mcp_tool")
    if action_type == "command" and not (isinstance(command, str) and command.startswith("/")):
        raise RegistryError(f"{item_id}: command action requires slash command")
    if action_type == "route" and not (isinstance(route, str) and route.startswith("/")):
        raise RegistryError(f"{item_id}: route action requires absolute route")
    if action_type == "mcp" and not isinstance(mcp_tool, str):
        raise RegistryError(f"{item_id}: mcp action requires mcp_tool")
    return RegistryAction(
        type=action_type,  # type: ignore[arg-type]
        label=label,
        command=command if isinstance(command, str) else None,
        route=route if isinstance(route, str) else None,
        mcp_tool=mcp_tool if isinstance(mcp_tool, str) else None,
    )


def load_registry(path: Path | None = None) -> SetupRegistry:
    registry_path = path or Path(__file__).resolve().parents[2] / "config" / "setup-items.yaml"
    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RegistryError("registry root must be a mapping")
    version = raw.get("version")
    if version != 1:
        raise RegistryError("registry version must be 1")
    raw_phases = raw.get("phases")
    if not isinstance(raw_phases, list) or not raw_phases:
        raise RegistryError("phases must be a non-empty list")

    seen_ids: set[str] = set()
    phases: list[RegistryPhase] = []
    for raw_phase in raw_phases:
        if not isinstance(raw_phase, dict):
            raise RegistryError("phase must be a mapping")
        phase_id = _require_text(raw_phase.get("id"), "phase.id")
        if phase_id not in {"foundation", "knowledge", "personalization"}:
            raise RegistryError(f"unsupported phase id {phase_id}")
        label = _require_text(raw_phase.get("label"), f"{phase_id}.label")
        raw_items = raw_phase.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise RegistryError(f"{phase_id}: items must be a non-empty list")
        items: list[RegistryItem] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                raise RegistryError(f"{phase_id}: item must be a mapping")
            item_id = _require_text(raw_item.get("id"), f"{phase_id}.item.id")
            if item_id in seen_ids:
                raise RegistryError(f"duplicate item id {item_id}")
            seen_ids.add(item_id)
            items.append(
                RegistryItem(
                    id=item_id,
                    label=_require_text(raw_item.get("label"), f"{item_id}.label"),
                    description=_require_text(raw_item.get("description"), f"{item_id}.description"),
                    probe=_require_text(raw_item.get("probe"), f"{item_id}.probe"),
                    action=_parse_action(raw_item.get("action"), item_id),
                )
            )
        phases.append(RegistryPhase(id=phase_id, label=label, items=items))  # type: ignore[arg-type]

    return SetupRegistry(version=version, phases=phases)
