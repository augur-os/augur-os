"""Dataclasses for setup-completeness status payloads."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


ItemStatusValue = Literal["done", "pending", "skipped", "regressed"]
PhaseId = Literal["foundation", "knowledge", "personalization"]
WidgetState = Literal["card", "bar", "chip", "alert"]
ActionType = Literal["command", "route", "mcp"]


@dataclass(frozen=True)
class ProbeResult:
    status: Literal["done", "pending"]
    details: str | None = None


@dataclass(frozen=True)
class ItemAction:
    type: ActionType
    label: str
    command: str | None = None
    route: str | None = None
    mcp_tool: str | None = None


@dataclass(frozen=True)
class ItemStatus:
    id: str
    label: str
    description: str
    status: ItemStatusValue
    action: ItemAction
    last_checked: str
    details: str | None = None


@dataclass(frozen=True)
class PhaseStatus:
    id: PhaseId
    label: str
    total: int
    completed: int
    pct: int
    items: list[ItemStatus] = field(default_factory=list)


@dataclass(frozen=True)
class SetupStatus:
    version: int
    computed_at: str
    total: int
    completed: int
    pct: int
    state: WidgetState
    ever_completed: bool
    phases: list[PhaseStatus] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
