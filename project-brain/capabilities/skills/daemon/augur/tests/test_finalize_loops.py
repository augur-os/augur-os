"""finalize_skill flips runner to auto and strips legacy frontmatter."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

_REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_DIR = _REPO_ROOT / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "routine_orchestrator"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    if str(_DIR) not in sys.path:
        sys.path.insert(0, str(_DIR))
    spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_DUAL_MULTI = """---
name: multi
x-augur-routine:
  id: a
  execution: tiered
  policy: adaptive
  callable: scripts/a.py
  loop: a
x-augur-routines:
- id: b
  execution: inline-session
  policy: oneshot
  callable: commands/b.md
x-augur-loops:
- id: a
  skill: multi
  loop_name: a
  automation: {trigger: nightly, runner: daemon, discover: scripts/a.py}
  memory: {trust: adaptive}
- id: b
  skill: multi
  loop_name: b
  automation: {trigger: manual, runner: auto, discover: commands/b.md}
  memory: {trust: oneshot}
---
# multi
body
"""


def test_finalize_flips_all_runners_and_strips_legacy(tmp_path: Path):
    mig = _load("migrate_to_standard_loop")
    skill = tmp_path / "multi"
    skill.mkdir()
    (skill / "SKILL.md").write_text(_DUAL_MULTI, encoding="utf-8")

    result = mig.finalize_skill(skill / "SKILL.md")

    assert result["loops"] == 2
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---\n")[1])
    assert "x-augur-routine" not in fm and "x-augur-routines" not in fm
    runners = {b["id"]: b["automation"]["runner"] for b in fm["x-augur-loops"]}
    assert runners == {"a": "auto", "b": "auto"}
    assert text.endswith("# multi\nbody\n")  # body preserved
