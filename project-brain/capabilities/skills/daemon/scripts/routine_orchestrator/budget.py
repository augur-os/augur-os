"""Per-subagent budget enforcement for the ADR-755 routine orchestrator."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any, Callable, Mapping

import yaml


DEFAULT_MAX_TURNS = 20
DEFAULT_SOFT_TIMEOUT_S = 600
DEFAULT_LLM_BUDGET_MULTIPLIER = 3


NowValue = float | int | datetime | Callable[[], float | int | datetime]


@dataclass
class Budget:
    max_turns: int
    soft_timeout_s: int
    consumed_turns: int = 0
    start_time: float = field(default_factory=monotonic)

    @classmethod
    def default(
        cls,
        loop: str,
        *,
        kind: str = "mechanical",
        config: Mapping[str, Any] | None = None,
        project_root: Path | str | None = None,
        now: NowValue | None = None,
    ) -> "Budget":
        loaded_config = dict(config) if config is not None else _load_config(project_root)
        llm_config = _mapping_at(loaded_config, "engine", "llm_escalation")
        loop_config = _mapping_at(loaded_config, "loops", loop)

        max_turns = _positive_int(llm_config.get("max_turns"), DEFAULT_MAX_TURNS)
        max_turns = _positive_int(loop_config.get("subagent_max_turns"), max_turns)
        soft_timeout_s = _positive_int(
            llm_config.get("timeout_s"),
            DEFAULT_SOFT_TIMEOUT_S,
        )

        if kind == "llm":
            multiplier = _positive_int(
                llm_config.get("budget_multiplier"),
                DEFAULT_LLM_BUDGET_MULTIPLIER,
            )
            max_turns *= multiplier

        return cls(
            max_turns=max_turns,
            soft_timeout_s=soft_timeout_s,
            consumed_turns=0,
            start_time=_coerce_now(now),
        )

    def consume(self, turns: int = 1) -> None:
        if turns < 0:
            raise ValueError("turns must be non-negative")
        self.consumed_turns += turns

    def check_remaining(self, *, now: NowValue | None = None) -> bool:
        if self.consumed_turns >= self.max_turns:
            return False
        elapsed = _coerce_now(now) - self.start_time
        return elapsed < self.soft_timeout_s


def _load_config(project_root: Path | str | None) -> dict[str, Any]:
    root = Path(project_root) if project_root is not None else _default_project_root()
    config_path = root / "config" / "system" / "adaptive_loops.yaml"
    if not config_path.is_file():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _default_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "config" / "system" / "adaptive_loops.yaml").is_file():
            return parent
    return Path.cwd()


def _mapping_at(config: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    value: Any = config
    for key in keys:
        if not isinstance(value, Mapping):
            return {}
        value = value.get(key, {})
    return value if isinstance(value, Mapping) else {}


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _coerce_now(now: NowValue | None) -> float:
    if now is None:
        return monotonic()
    value = now() if callable(now) else now
    if isinstance(value, datetime):
        return value.timestamp()
    return float(value)


__all__ = ["Budget"]
