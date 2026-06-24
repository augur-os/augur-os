"""list_routines builds Routine records from canonical x-augur-loop(s)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_MODULE_PATH = _REPO_ROOT / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "routine_orchestrator" / "registry.py"


def _load_registry():
    spec = importlib.util.spec_from_file_location("registry_lfl", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _skill(root: Path, name: str, body: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


_LOOP_ONLY = """---
name: loops-skill
x-augur-loops:
- id: orchestrated
  skill: loops-skill
  loop_name: orchestrated
  automation:
    trigger: nightly
    runner: auto
    discover: scripts/routine_orchestrator/orchestrator.py
  memory:
    trust: adaptive
- id: prompted
  skill: loops-skill
  loop_name: prompted
  automation:
    trigger: manual
    runner: auto
    discover: commands/prompted.md
  memory:
    trust: oneshot
---
# loops-skill
"""

_DUAL = """---
name: dual-skill
x-augur-routine:
  id: shared
  execution: tiered
  policy: adaptive
  callable: scripts/x.py
  loop: shared
x-augur-loop:
  id: shared
  skill: dual-skill
  loop_name: shared
  automation:
    trigger: nightly
    runner: auto
    discover: scripts/x.py
  memory:
    trust: adaptive
---
# dual-skill
"""


def test_list_routines_synthesizes_from_loops(tmp_path: Path):
    registry = _load_registry()
    _skill(tmp_path, "loops-skill", _LOOP_ONLY)
    routines = {r.id: r for r in registry.list_routines(skills_root=tmp_path)}
    assert set(routines) == {"orchestrated", "prompted"}
    assert routines["orchestrated"].execution == "tiered"      # .py discover => orchestrator kind
    assert routines["prompted"].execution == "inline-session"  # .md discover => prompt kind
    assert routines["orchestrated"].policy == "adaptive"
    assert routines["prompted"].policy == "oneshot"
    assert routines["orchestrated"].loop == "orchestrated"


def test_dual_state_lists_once_loop_wins(tmp_path: Path):
    registry = _load_registry()
    _skill(tmp_path, "dual-skill", _DUAL)
    routines = [r for r in registry.list_routines(skills_root=tmp_path) if r.id == "shared"]
    assert len(routines) == 1  # no collision: loop covers the legacy id
    assert routines[0].execution == "tiered"
