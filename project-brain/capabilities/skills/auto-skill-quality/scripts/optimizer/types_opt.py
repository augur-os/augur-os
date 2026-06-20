"""Shared optimizer dataclasses (one import home, no logic)."""
from dataclasses import dataclass
from typing import Any


@dataclass
class ReplayCase:
    inputs: dict[str, Any]
    prior_output: str | None = None
    source: str = "unknown"  # "mcp-log" | "cli-log" | "seed-eval" | "curated-eval"


@dataclass
class RunResult:
    output: str
    wall_ms: float
    tokens: int
    llm_calls: int
    ok: bool = True
    error: str | None = None


@dataclass
class CaseScore:
    accuracy: float
    tokens: int
    wall_ms: float
