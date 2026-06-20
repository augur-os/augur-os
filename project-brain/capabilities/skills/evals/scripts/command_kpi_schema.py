"""Automatic KPI scenario schema for Augur command evals."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCENARIO_SCHEMA = "command.kpi.scenario.v1"
PACK_SCHEMA = "command.kpi.pack.v1"
THRESHOLDS_SCHEMA = "command.kpi.thresholds.v1"

CANONICAL_COMMANDS = {"ask", "keep", "discover", "adr", "dev", "routines", "sweep"}
PRIMARY_CLIENTS = {"claude", "codex", "gemini", "engine"}

MIN_SCENARIOS_BY_COMMAND = {
    "ask": 4,
    "keep": 5,
    "discover": 2,
    "adr": 2,
    "dev": 2,
    "routines": 2,
    "sweep": 2,
}


@dataclass(frozen=True)
class KPIThresholds:
    min_total: int = 18
    required_consecutive_passes: int = 3
    route_decision_max_ms: int = 3000
    simple_local_action_max_ms: int = 30000
    command_without_progress_max_ms: int = 120000
    command_max_ms: dict[str, int] = field(
        default_factory=lambda: {
            "ask": 60000,
            "keep": 30000,
            "discover": 10000,
            "adr": 15000,
            "dev": 60000,
            "routines": 15000,
            "sweep": 30000,
        }
    )


@dataclass(frozen=True)
class CommandScenario:
    id: str
    command: str
    client: str
    input_class: str
    input: str
    assertions: dict[str, Any]
    max_duration_ms: int | None = None
    allow_cloud_route: bool = False
    private_refs: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CommandScenario":
        if payload.get("_schema") != SCENARIO_SCHEMA:
            raise ValueError(f"expected {SCENARIO_SCHEMA}")

        scenario_id = str(payload.get("id") or "").strip()
        if not scenario_id:
            raise ValueError("scenario id is required")

        command = str(payload.get("command") or "").strip().lstrip("/")
        if command not in CANONICAL_COMMANDS:
            raise ValueError(f"scenario command must be canonical: {command}")

        client = str(payload.get("client") or "engine").strip()
        if client not in PRIMARY_CLIENTS:
            raise ValueError(f"scenario client must be one of {sorted(PRIMARY_CLIENTS)}")

        assertions = payload.get("assertions") or {}
        if not isinstance(assertions, dict):
            raise ValueError("assertions must be an object")

        private_refs = payload.get("private_refs") or []
        if not isinstance(private_refs, list) or not all(isinstance(item, str) for item in private_refs):
            raise ValueError("private_refs must be a list of strings")

        max_duration_ms = payload.get("max_duration_ms")
        if max_duration_ms is not None:
            max_duration_ms = int(max_duration_ms)

        return cls(
            id=scenario_id,
            command=command,
            client=client,
            input_class=str(payload.get("input_class") or "").strip(),
            input=str(payload.get("input") or ""),
            assertions=assertions,
            max_duration_ms=max_duration_ms,
            allow_cloud_route=bool(payload.get("allow_cloud_route", False)),
            private_refs=list(private_refs),
        )


@dataclass(frozen=True)
class GateResult:
    passed: bool
    issues: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "issues": list(self.issues)}


def validate_private_scenario_path(path: Path, *, documents_dir: Path) -> None:
    try:
        path.resolve().relative_to(documents_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"scenario path is outside private documents root: {path}") from exc


def evaluate_gate(
    aggregate: dict[str, Any],
    thresholds: KPIThresholds,
    *,
    consecutive_passes: int,
) -> GateResult:
    issues: list[dict[str, Any]] = []
    total = int(aggregate.get("total") or 0)

    if total < thresholds.min_total:
        issues.append(
            {
                "code": "insufficient_total",
                "actual": total,
                "expected": thresholds.min_total,
            }
        )
    if int(aggregate.get("fail_count") or 0) != 0:
        issues.append({"code": "fail_count_nonzero", "actual": aggregate.get("fail_count")})
    if int(aggregate.get("warn_count") or 0) != 0:
        issues.append({"code": "warn_count_nonzero", "actual": aggregate.get("warn_count")})
    if float(aggregate.get("pass_rate") or 0.0) < 1.0:
        issues.append({"code": "pass_rate_below_1", "actual": aggregate.get("pass_rate")})

    by_command = aggregate.get("by_command") or {}
    for command, minimum in MIN_SCENARIOS_BY_COMMAND.items():
        count = int((by_command.get(command) or {}).get("total") or 0)
        if count < minimum:
            issues.append(
                {
                    "code": "command_undercovered",
                    "command": command,
                    "actual": count,
                    "expected": minimum,
                }
            )

    if consecutive_passes < thresholds.required_consecutive_passes:
        issues.append(
            {
                "code": "stability_not_met",
                "actual": consecutive_passes,
                "expected": thresholds.required_consecutive_passes,
            }
        )

    return GateResult(passed=not issues, issues=issues)
