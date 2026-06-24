"""x-augur-loop parsing + runner dispatch in the registry."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_MODULE_PATH = _REPO_ROOT / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "routine_orchestrator" / "registry.py"

_NEW_SKILL = """---
name: loop-skill
x-augur-loop:
  id: knowledge
  skill: loop-skill
  loop_name: knowledge
  automation:
    trigger: nightly
    runner: daemon
    discover: scripts/scan.py
  subagents:
    fix: mechanical
  memory:
    trust: adaptive
---
# loop-skill
"""


def _load_registry():
    spec = importlib.util.spec_from_file_location("registry_sl", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_skill(root: Path, name: str, body: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


def test_resolve_loop_parses_x_augur_loop(tmp_path: Path):
    registry = _load_registry()
    _make_skill(tmp_path, "loop-skill", _NEW_SKILL)
    loop = registry.resolve_loop("knowledge", skills_root=tmp_path)
    assert loop.automation.runner == "daemon"
    assert loop.subagents.fix == "mechanical"


def test_dispatch_routes_daemon_loop_through_orchestrator(tmp_path: Path, monkeypatch):
    registry = _load_registry()
    _make_skill(tmp_path, "loop-skill", _NEW_SKILL)
    captured = {}

    def fake_orchestrate_run(name, **kw):
        captured["name"] = name
        return {"ok": True}

    monkeypatch.setattr(registry._load_orchestrator(), "orchestrate_run", fake_orchestrate_run, raising=False)
    result = registry.dispatch("knowledge", skills_root=tmp_path)
    assert result == {"ok": True}
    assert captured["name"] == "knowledge"
