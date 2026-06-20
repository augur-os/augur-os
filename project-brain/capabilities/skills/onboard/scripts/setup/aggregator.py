"""Run setup probes and derive the widget state."""

from __future__ import annotations

import importlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .registry import load_registry
from .state import load_persisted_state, save_ever_completed
from .types import ItemAction, ItemStatus, PhaseStatus, ProbeResult, SetupStatus, WidgetState


_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "setup-items.yaml"
_CACHE_TTL_SECONDS = 300
_cache: dict[str, object] = {"ts": 0.0, "value": None}


def clear_cache() -> None:
    _cache["ts"] = 0.0
    _cache["value"] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_probe(probe_path: str) -> Callable[[], ProbeResult]:
    module_name, func_name = probe_path.rsplit(".", 1)
    package = __package__ or "setup"
    module = importlib.import_module(f"{package}.probes.{module_name}")
    return getattr(module, func_name)


def _pct(completed: int, total: int) -> int:
    if total <= 0:
        return 100
    return int(round((completed / total) * 100))


def _derive_widget_state(*, pct: int, ever_completed: bool, has_pending: bool) -> WidgetState:
    if ever_completed and has_pending:
        return "alert"
    if pct >= 100:
        return "chip"
    if pct >= 60:
        return "bar"
    return "card"


def compute_setup_status(*, skip_cache: bool = False) -> SetupStatus:
    now = time.time()
    cached = _cache.get("value")
    if not skip_cache and cached is not None and now - float(_cache["ts"]) < _CACHE_TTL_SECONDS:
        return cached  # type: ignore[return-value]

    registry = load_registry(_REGISTRY_PATH)
    persisted = load_persisted_state()
    skipped = set(persisted.skipped)
    phases: list[PhaseStatus] = []
    total = 0
    completed = 0
    has_pending = False

    for phase in registry.phases:
        phase_total = 0
        phase_completed = 0
        item_statuses: list[ItemStatus] = []
        for item in phase.items:
            action = ItemAction(
                type=item.action.type,
                label=item.action.label,
                command=item.action.command,
                route=item.action.route,
                mcp_tool=item.action.mcp_tool,
            )
            if item.id in skipped:
                item_statuses.append(
                    ItemStatus(
                        id=item.id,
                        label=item.label,
                        description=item.description,
                        status="skipped",
                        action=action,
                        last_checked=_now_iso(),
                    )
                )
                continue

            phase_total += 1
            total += 1
            try:
                result = _load_probe(item.probe)()
            except Exception as exc:
                result = ProbeResult(status="pending", details=f"probe error: {exc}")

            if result.status == "done":
                item_state = "done"
                phase_completed += 1
                completed += 1
            else:
                item_state = "regressed" if persisted.ever_completed else "pending"
                has_pending = True

            item_statuses.append(
                ItemStatus(
                    id=item.id,
                    label=item.label,
                    description=item.description,
                    status=item_state,
                    action=action,
                    last_checked=_now_iso(),
                    details=result.details,
                )
            )
        phases.append(
            PhaseStatus(
                id=phase.id,
                label=phase.label,
                total=phase_total,
                completed=phase_completed,
                pct=_pct(phase_completed, phase_total),
                items=item_statuses,
            )
        )

    pct = _pct(completed, total)
    ever_completed = persisted.ever_completed
    if pct >= 100 and not ever_completed:
        save_ever_completed(True)
        ever_completed = True

    status = SetupStatus(
        version=1,
        computed_at=_now_iso(),
        total=total,
        completed=completed,
        pct=pct,
        state=_derive_widget_state(pct=pct, ever_completed=ever_completed, has_pending=has_pending),
        ever_completed=ever_completed,
        phases=phases,
    )
    _cache["ts"] = now
    _cache["value"] = status
    return status
