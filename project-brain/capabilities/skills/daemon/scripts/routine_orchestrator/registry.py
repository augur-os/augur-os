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

ALLOWED_EXECUTIONS = frozenset({"tiered", "inline-session"})
ALLOWED_POLICIES = frozenset({"adaptive", "oneshot", "observability-only"})
REQUIRED_FIELDS = ("id", "execution", "policy", "callable")


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
    raw: dict[str, Any] = field(default_factory=dict)


def list_routines(
    *,
    skills_root: Path | str | None = None,
    skills_roots: list[Path | str] | tuple[Path | str, ...] | None = None,
) -> list[Routine]:
    """Return all declared routines sorted by flat routine id."""
    roots = _resolve_skill_roots(skills_root=skills_root, skills_roots=skills_roots)
    declarations: dict[str, Routine] = {}
    for root in roots:
        for skill_md in sorted(root.glob("*/SKILL.md")):
            metadata = _frontmatter(skill_md)
            for index, declaration in enumerate(_routine_declarations(metadata)):
                routine = _resolve_declaration(skill_md, declaration, index=index)
                existing = declarations.get(routine.id)
                if existing is not None:
                    raise RoutineIdCollision(
                        f"routine id {routine.id!r} declared by both "
                        f"{existing.skill_name!r} and {routine.skill_name!r}"
                    )
                declarations[routine.id] = routine
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
    """Dispatch a routine through its declared execution model."""
    skills_root = kwargs.pop("skills_root", None)
    skills_roots = kwargs.pop("skills_roots", None)
    routine = get_routine(routine_id, skills_root=skills_root, skills_roots=skills_roots)
    if routine.execution == "tiered":
        return _orchestrate_tiered_routine(routine, kwargs)
    if routine.execution == "inline-session":
        return _render_inline_session_routine(routine)
    raise RoutineValidationError(
        f"routine {routine_id!r} has unsupported execution {routine.execution!r}"
    )


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


def _routine_declarations(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    singular = metadata.get("x-augur-routine")
    plural = metadata.get("x-augur-routines")
    if singular is not None:
        if not isinstance(singular, dict):
            raise RoutineValidationError("x-augur-routine must be a mapping")
        declarations.append(singular)
    if plural is not None:
        if not isinstance(plural, list):
            raise RoutineValidationError("x-augur-routines must be a list")
        for item in plural:
            if not isinstance(item, dict):
                raise RoutineValidationError("x-augur-routines entries must be mappings")
            declarations.append(item)
    return declarations


def _resolve_declaration(skill_md: Path, declaration: dict[str, Any], *, index: int) -> Routine:
    skill_root = skill_md.parent
    skill_name = _skill_name(skill_md, declaration)
    for field_name in REQUIRED_FIELDS:
        if not declaration.get(field_name):
            raise RoutineValidationError(
                f"{skill_name} routine declaration #{index + 1} missing {field_name!r}"
            )

    routine_id = str(declaration["id"])
    execution = str(declaration["execution"])
    policy = str(declaration["policy"])
    callable_ref = str(declaration["callable"])

    if execution not in ALLOWED_EXECUTIONS:
        raise RoutineValidationError(
            f"{skill_name} routine {routine_id!r} has invalid execution {execution!r}"
        )
    if policy not in ALLOWED_POLICIES:
        raise RoutineValidationError(
            f"{skill_name} routine {routine_id!r} has invalid policy {policy!r}"
        )

    return Routine(
        id=routine_id,
        execution=execution,
        policy=policy,
        callable=callable_ref,
        skill_name=skill_name,
        skill_root=skill_root,
        callable_path=skill_root / callable_ref,
        loop=_optional_str(declaration.get("loop")),
        hub=_optional_str(declaration.get("hub")),
        description=_optional_str(declaration.get("description")),
        fan_out_threshold=_optional_int(declaration.get("fan_out_threshold")),
        budget_max_turns=_optional_int(declaration.get("budget_max_turns")),
        raw=dict(declaration),
    )


def _orchestrate_tiered_routine(routine: Routine, kwargs: dict[str, Any]) -> Any:
    orchestrator = _load_orchestrator()
    return orchestrator.orchestrate_run(routine.loop or routine.id, **kwargs)


def _render_inline_session_routine(routine: Routine) -> dict[str, Any]:
    if not routine.callable_path.is_file():
        raise RoutineValidationError(
            f"routine {routine.id!r} prompt file not found: {routine.callable_path}"
        )
    return {
        "success": True,
        "routine_id": routine.id,
        "execution": routine.execution,
        "policy": routine.policy,
        "callable_path": str(routine.callable_path),
        "render_prompt": routine.callable_path.read_text(encoding="utf-8"),
    }


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


def _skill_name(skill_md: Path, declaration: dict[str, Any]) -> str:
    metadata = _frontmatter(skill_md)
    return str(metadata.get("name") or declaration.get("skill") or skill_md.parent.name)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


__all__ = [
    "ALLOWED_EXECUTIONS",
    "ALLOWED_POLICIES",
    "Routine",
    "RoutineIdCollision",
    "RoutineNotFound",
    "RoutineRegistryError",
    "RoutineValidationError",
    "dispatch",
    "get_routine",
    "list_routines",
]
