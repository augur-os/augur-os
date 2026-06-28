"""Canonical standard-loop model (article 5-part anatomy) and parser."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ALLOWED_RUNNERS = frozenset({"daemon", "claude", "codex", "auto"})
ALLOWED_FIX = frozenset({"mechanical", "subagent"})
ALLOWED_ISOLATION = frozenset({"worktree", "in-place"})
# ADR-818 phase 2: where an in-place loop writes. Picks the guardrail policy in
# the in-place runner (vault -> vault repo + ADR-816 lock; runtime -> no repo
# commit, external configs via sanctioned tools; repo -> code repo; mixed ->
# per-finding routing). Worktree loops are implicitly "repo".
ALLOWED_SURFACE = frozenset({"repo", "vault", "runtime", "mixed"})


class LoopValidationError(Exception):
    """Raised when an x-augur-loop declaration has invalid schema."""


@dataclass(frozen=True)
class Automation:
    trigger: str
    runner: str
    discover: str | None = None


@dataclass(frozen=True)
class Isolation:
    mode: str = "in-place"
    branch: str | None = None
    # ADR-818 phase 2 execution surface (see ALLOWED_SURFACE). Defaults to "repo"
    # for worktree loops and "mixed" for in-place loops when unset.
    surface: str = "repo"


@dataclass(frozen=True)
class Subagents:
    scan: str | None = None
    fix: str = "subagent"
    verify: str | None = None


@dataclass(frozen=True)
class Memory:
    ledger: str | None = None
    escalation: str | None = None
    trust: str = "adaptive"


@dataclass(frozen=True)
class StandardLoop:
    id: str
    skill: str
    automation: Automation
    isolation: Isolation
    subagents: Subagents
    memory: Memory
    loop_name: str | None = None
    discover_path: str | None = None
    connectors: tuple[str, ...] = ()
    budget: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _str_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def parse_standard_loop(declaration: dict[str, Any], *, skill_name: str, skill_root: Any = None) -> StandardLoop:
    if not declaration.get("id"):
        raise LoopValidationError(f"{skill_name} x-augur-loop missing 'id'")
    auto = declaration.get("automation")
    if not isinstance(auto, dict):
        raise LoopValidationError(f"{skill_name} x-augur-loop missing 'automation' mapping")
    runner = str(auto.get("runner", ""))
    if runner not in ALLOWED_RUNNERS:
        raise LoopValidationError(
            f"{skill_name} loop {declaration['id']!r} invalid runner {runner!r}"
        )
    if not auto.get("trigger"):
        raise LoopValidationError(f"{skill_name} loop {declaration['id']!r} missing automation.trigger")

    iso = declaration.get("isolation") or {}
    mode = str(iso.get("mode", "in-place"))
    if mode not in ALLOWED_ISOLATION:
        raise LoopValidationError(f"{skill_name} loop {declaration['id']!r} invalid isolation.mode {mode!r}")
    surface = str(iso.get("surface") or ("mixed" if mode == "in-place" else "repo"))
    if surface not in ALLOWED_SURFACE:
        raise LoopValidationError(f"{skill_name} loop {declaration['id']!r} invalid isolation.surface {surface!r}")

    sub = declaration.get("subagents") or {}
    fix = str(sub.get("fix", "subagent"))
    if fix not in ALLOWED_FIX:
        raise LoopValidationError(f"{skill_name} loop {declaration['id']!r} invalid subagents.fix {fix!r}")

    mem = declaration.get("memory") or {}
    connectors = tuple(str(c) for c in (declaration.get("connectors") or ()))

    discover = _str_or_none(auto.get("discover"))
    discover_path = None
    if skill_root is not None and discover:
        discover_path = str(Path(skill_root) / discover)

    return StandardLoop(
        id=str(declaration["id"]),
        skill=str(declaration.get("skill") or skill_name),
        automation=Automation(
            trigger=str(auto["trigger"]),
            runner=runner,
            discover=discover,
        ),
        isolation=Isolation(mode=mode, branch=_str_or_none(iso.get("branch")), surface=surface),
        subagents=Subagents(
            scan=_str_or_none(sub.get("scan")),
            fix=fix,
            verify=_str_or_none(sub.get("verify")),
        ),
        memory=Memory(
            ledger=_str_or_none(mem.get("ledger")),
            escalation=_str_or_none(mem.get("escalation")),
            trust=str(mem.get("trust", "adaptive")),
        ),
        loop_name=_str_or_none(declaration.get("loop_name")),
        discover_path=discover_path,
        connectors=connectors,
        budget=declaration.get("budget") if isinstance(declaration.get("budget"), dict) else None,
        raw=dict(declaration),
    )


__all__ = [
    "ALLOWED_RUNNERS",
    "Automation",
    "Isolation",
    "LoopValidationError",
    "Memory",
    "StandardLoop",
    "Subagents",
    "parse_standard_loop",
]
