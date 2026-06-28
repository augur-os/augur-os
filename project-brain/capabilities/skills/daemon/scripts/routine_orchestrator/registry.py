"""ADR-758 routine declaration registry.

Discovers routine wrapper declarations from skill-local ``SKILL.md``
frontmatter. Individual auto-command discovery remains owned by the existing
adaptive/orchestrator scan path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    from . import loop_model, loop_runner
except ImportError:  # pragma: no cover - direct-path load
    import sys as _sys

    _DIR = Path(__file__).parent
    if str(_DIR) not in _sys.path:
        _sys.path.insert(0, str(_DIR))
    import loop_model  # type: ignore[no-redef]
    import loop_runner  # type: ignore[no-redef]


ALLOWED_RUNNERS = loop_model.ALLOWED_RUNNERS


class RoutineRegistryError(Exception):
    """Base exception for routine registry failures."""


class RoutineValidationError(RoutineRegistryError):
    """Raised when a routine declaration has invalid schema."""


class RoutineIdCollision(RoutineRegistryError):
    """Raised when two routine declarations use the same flat id."""


class RoutineNotFound(RoutineRegistryError):
    """Raised when no routine declaration matches an id."""


@dataclass(frozen=True)
class Routine:
    """Resolved routine wrapper declaration."""

    id: str
    execution: str
    policy: str
    callable: str
    skill_name: str
    skill_root: Path
    callable_path: Path
    loop: str | None = None
    hub: str | None = None
    description: str | None = None
    fan_out_threshold: int | None = None
    budget_max_turns: int | None = None
    runner: str = ""
    # ADR-818: execution surface. "worktree" loops are eligible for the
    # /a-loops all isolated-worktree fan-out; "in-place" loops act on the live
    # vault/runtime/external state and are routed to the daemon instead.
    # Defaults to "worktree" so undeclared (code) loops keep fanning out.
    isolation_mode: str = "worktree"
    # ADR-818 phase 2: in-place write surface (repo|vault|runtime|mixed). Picks
    # the guardrail policy in the in-place runner. "repo" for worktree loops.
    execution_surface: str = "repo"
    raw: dict[str, Any] = field(default_factory=dict)


def _routine_from_loop(skill_md: Path, block: dict[str, Any], *, skill_name: str) -> Routine:
    loop = loop_model.parse_standard_loop(block, skill_name=skill_name, skill_root=skill_md.parent)
    discover = loop.automation.discover or ""
    execution = "inline-session" if discover.endswith(".md") else "tiered"
    skill_root = skill_md.parent
    # ADR-818: a loop is in-place ONLY when it explicitly declares
    # isolation.mode: in-place. Undeclared loops default to worktree so the
    # existing code loops keep fanning out (loop_model parses an undeclared
    # mode as "in-place", so we read the explicit value from the raw block).
    iso_block = block.get("isolation") or {}
    isolation_mode = str(iso_block.get("mode") or "worktree")
    execution_surface = str(
        iso_block.get("surface") or ("mixed" if isolation_mode == "in-place" else "repo")
    )
    return Routine(
        id=loop.id,
        execution=execution,
        policy=loop.memory.trust,
        callable=discover,
        skill_name=skill_name,
        skill_root=skill_root,
        callable_path=(skill_root / discover) if discover else skill_root,
        loop=loop.loop_name,
        hub=None,
        description=None,
        fan_out_threshold=None,
        budget_max_turns=None,
        runner=loop.automation.runner,
        isolation_mode=isolation_mode,
        execution_surface=execution_surface,
        raw=dict(block),
    )


def _register_routine(declarations: dict[str, "Routine"], sources: dict[str, str], routine: "Routine") -> None:
    existing = declarations.get(routine.id)
    if existing is not None:
        raise RoutineIdCollision(
            f"routine id {routine.id!r} declared by both {sources[routine.id]!r} and {routine.skill_name!r}"
        )
    declarations[routine.id] = routine
    sources[routine.id] = routine.skill_name


def list_routines(
    *,
    skills_root: Path | str | None = None,
    skills_roots: list[Path | str] | tuple[Path | str, ...] | None = None,
) -> list[Routine]:
    """Return all routines (canonical x-augur-loop(s)) sorted by id."""
    roots = _resolve_skill_roots(skills_root=skills_root, skills_roots=skills_roots)
    declarations: dict[str, Routine] = {}
    sources: dict[str, str] = {}
    # Canonical x-augur-loop(s) are the source of truth.
    for root in roots:
        for skill_md in sorted(root.glob("*/SKILL.md")):
            metadata = _frontmatter(skill_md)
            skill_name = str(metadata.get("name") or skill_md.parent.name)
            for block in _loop_declarations(metadata):
                routine = _routine_from_loop(skill_md, block, skill_name=skill_name)
                _register_routine(declarations, sources, routine)
    return [declarations[routine_id] for routine_id in sorted(declarations)]


def get_routine(
    routine_id: str,
    *,
    skills_root: Path | str | None = None,
    skills_roots: list[Path | str] | tuple[Path | str, ...] | None = None,
) -> Routine:
    """Resolve one routine by id."""
    for routine in list_routines(skills_root=skills_root, skills_roots=skills_roots):
        if routine.id == routine_id:
            return routine
    raise RoutineNotFound(f"routine {routine_id!r} not found")


def dispatch(routine_id: str, **kwargs: Any) -> Any:
    """Dispatch a routine/loop through its resolved runner."""
    skills_root = kwargs.pop("skills_root", None)
    skills_roots = kwargs.pop("skills_roots", None)
    loop = resolve_loop(routine_id, skills_root=skills_root, skills_roots=skills_roots)
    runner = loop_runner.resolve_runner(loop, orchestrate=_load_orchestrator().orchestrate_run)
    return runner.run(loop, **kwargs)


def _default_skills_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_skill_roots() -> list[Path]:
    try:
        from src.config.paths import get_managed_skill_source_dirs

        roots = [Path(root) for root in get_managed_skill_source_dirs()]
        if roots:
            return roots
    except Exception:
        pass
    return [_default_skills_root()]


def _resolve_skill_roots(
    *,
    skills_root: Path | str | None,
    skills_roots: list[Path | str] | tuple[Path | str, ...] | None,
) -> list[Path]:
    if skills_root is not None and skills_roots is not None:
        raise RoutineValidationError("pass either skills_root or skills_roots, not both")
    if skills_root is not None:
        return [Path(skills_root)]
    if skills_roots is not None:
        return [Path(root) for root in skills_roots]
    return _default_skill_roots()


def _frontmatter(skill_md: Path) -> dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    data = yaml.safe_load(text[4:end]) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _loop_declarations(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all canonical x-augur-loop / x-augur-loops blocks in a skill."""
    blocks: list[dict[str, Any]] = []
    single = metadata.get("x-augur-loop")
    if single is not None:
        if not isinstance(single, dict):
            raise RoutineValidationError("x-augur-loop must be a mapping")
        blocks.append(single)
    plural = metadata.get("x-augur-loops")
    if plural is not None:
        if not isinstance(plural, list):
            raise RoutineValidationError("x-augur-loops must be a list")
        for item in plural:
            if not isinstance(item, dict):
                raise RoutineValidationError("x-augur-loops entries must be mappings")
            blocks.append(item)
    return blocks


def resolve_loop(
    routine_id: str,
    *,
    skills_root: Path | str | None = None,
    skills_roots: list[Path | str] | tuple[Path | str, ...] | None = None,
) -> "loop_model.StandardLoop":
    """Return the StandardLoop for an id by parsing x-augur-loop(s)."""
    roots = _resolve_skill_roots(skills_root=skills_root, skills_roots=skills_roots)
    for root in roots:
        for skill_md in sorted(root.glob("*/SKILL.md")):
            metadata = _frontmatter(skill_md)
            for block in _loop_declarations(metadata):
                if str(block.get("id")) == routine_id:
                    skill_name = str(metadata.get("name") or skill_md.parent.name)
                    return loop_model.parse_standard_loop(
                        block, skill_name=skill_name, skill_root=skill_md.parent
                    )
    raise RoutineNotFound(f"loop {routine_id!r} not found")


def _load_orchestrator() -> Any:
    try:
        from . import orchestrator

        return orchestrator
    except Exception:
        import importlib
        import sys

        scripts_dir = Path(__file__).resolve().parents[1]
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        return importlib.import_module("routine_orchestrator.orchestrator")


__all__ = [
    "ALLOWED_RUNNERS",
    "Routine",
    "RoutineIdCollision",
    "RoutineNotFound",
    "RoutineRegistryError",
    "RoutineValidationError",
    "dispatch",
    "get_routine",
    "list_routines",
    "resolve_loop",
]
