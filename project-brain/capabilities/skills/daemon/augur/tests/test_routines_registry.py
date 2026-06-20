"""Tests for the ADR-758 routine declaration registry."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_MODULE_PATH = _REPO_ROOT / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "routine_orchestrator" / "registry.py"
_FIXTURES = Path(__file__).with_name("fixtures") / "routine-skills"


def _load_registry():
    assert _MODULE_PATH.is_file(), "routine_orchestrator/registry.py must exist"
    spec = importlib.util.spec_from_file_location("routine_registry_under_test", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _copy_skill(src: Path, dest_root: Path) -> Path:
    dest = dest_root / src.name
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text((src / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def test_list_routines_walks_all_skill_md_blocks(tmp_path: Path) -> None:
    registry = _load_registry()
    _copy_skill(_FIXTURES / "tiered-skill", tmp_path)
    _copy_skill(_FIXTURES / "inline-skill", tmp_path)

    routines = registry.list_routines(skills_root=tmp_path)

    assert [routine.id for routine in routines] == ["code-quality", "dream", "testing"]
    assert {routine.skill_name for routine in routines} == {"inline-skill", "tiered-skill"}


def test_list_routines_walks_multiple_skill_roots(tmp_path: Path) -> None:
    registry = _load_registry()
    shared_root = tmp_path / "shared"
    private_root = tmp_path / "private"
    _copy_skill(_FIXTURES / "tiered-skill", shared_root)
    _copy_skill(_FIXTURES / "inline-skill", private_root)

    routines = registry.list_routines(skills_roots=[shared_root, private_root])

    assert [routine.id for routine in routines] == ["code-quality", "dream", "testing"]
    assert registry.get_routine("dream", skills_roots=[shared_root, private_root]).skill_root.parent == private_root


def test_singular_and_plural_schema_both_supported(tmp_path: Path) -> None:
    registry = _load_registry()
    _copy_skill(_FIXTURES / "tiered-skill", tmp_path)
    _copy_skill(_FIXTURES / "inline-skill", tmp_path)

    routines = {routine.id: routine for routine in registry.list_routines(skills_root=tmp_path)}

    assert routines["dream"].execution == "inline-session"
    assert routines["testing"].execution == "tiered"
    assert routines["code-quality"].policy == "adaptive"


def test_get_routine_by_id_returns_resolved_record(tmp_path: Path) -> None:
    registry = _load_registry()
    tiered_root = _copy_skill(_FIXTURES / "tiered-skill", tmp_path)

    routine = registry.get_routine("testing", skills_root=tmp_path)

    assert routine.id == "testing"
    assert routine.loop == "testing"
    assert routine.callable == "scripts/testing.py"
    assert routine.callable_path == tiered_root / "scripts" / "testing.py"


def test_id_collision_raises_loud(tmp_path: Path) -> None:
    registry = _load_registry()
    _copy_skill(_FIXTURES / "tiered-skill", tmp_path)
    _copy_skill(_FIXTURES / "colliding-skill", tmp_path)

    with pytest.raises(registry.RoutineIdCollision, match="testing"):
        registry.list_routines(skills_root=tmp_path)


def test_missing_required_field_raises_validation_error(tmp_path: Path) -> None:
    registry = _load_registry()
    skill = tmp_path / "missing-callable"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        """---
name: missing-callable
x-augur-routine:
  id: broken
  execution: tiered
  policy: adaptive
---
""",
        encoding="utf-8",
    )

    with pytest.raises(registry.RoutineValidationError, match="callable"):
        registry.list_routines(skills_root=tmp_path)


def test_unknown_execution_model_raises(tmp_path: Path) -> None:
    registry = _load_registry()
    skill = tmp_path / "unknown-execution"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        """---
name: unknown-execution
x-augur-routine:
  id: broken
  execution: batch
  policy: adaptive
  callable: scripts/run.py
---
""",
        encoding="utf-8",
    )

    with pytest.raises(registry.RoutineValidationError, match="execution"):
        registry.list_routines(skills_root=tmp_path)


def test_unknown_policy_raises(tmp_path: Path) -> None:
    registry = _load_registry()
    skill = tmp_path / "unknown-policy"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        """---
name: unknown-policy
x-augur-routine:
  id: broken
  execution: tiered
  policy: nightly
  callable: scripts/run.py
---
""",
        encoding="utf-8",
    )

    with pytest.raises(registry.RoutineValidationError, match="policy"):
        registry.list_routines(skills_root=tmp_path)


def test_repo_shared_skill_routine_declarations_cover_non_private_manifest_ids() -> None:
    registry = _load_registry()
    shared_skills_root = _REPO_ROOT / "project-brain" / "capabilities" / "skills"

    routines = registry.list_routines(skills_root=shared_skills_root)

    assert [routine.id for routine in routines] == [
        "auto-agent-digest",
        "code-quality",
        "command-evolution",
        "dream",
        "duplication",
        "evals",
        "goal-loop",
        "hardening",
        "knowledge-enrichment",
        "observability",
        "page-health",
        "self-heal",
        "skill-quality",
        "skill-standards",
        "testing",
        "ui-quality",
    ]
