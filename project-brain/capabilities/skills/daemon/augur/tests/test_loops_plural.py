"""Plural x-augur-loops: registry reads a list."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_DIR = _REPO_ROOT / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "routine_orchestrator"

if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_PLURAL_SKILL = """---
name: plural-skill
x-augur-loops:
- id: alpha
  skill: plural-skill
  loop_name: alpha
  automation:
    trigger: nightly
    runner: daemon
  memory:
    trust: adaptive
- id: beta
  skill: plural-skill
  loop_name: beta
  automation:
    trigger: weekly
    runner: auto
  memory:
    trust: oneshot
---
# plural-skill
"""


def _make_skill(root: Path, name: str, body: str) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    return d


def test_registry_resolves_a_loop_from_plural_list(tmp_path: Path):
    registry = _load("registry")
    _make_skill(tmp_path, "plural-skill", _PLURAL_SKILL)
    alpha = registry.resolve_loop("alpha", skills_root=tmp_path)
    beta = registry.resolve_loop("beta", skills_root=tmp_path)
    assert alpha.automation.runner == "daemon"
    assert beta.automation.runner == "auto"
    assert beta.memory.trust == "oneshot"
