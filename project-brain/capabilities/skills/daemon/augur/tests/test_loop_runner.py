"""Tests for runner resolution and the daemon runner."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_DIR = _REPO_ROOT / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "routine_orchestrator"


def _load(name: str):
    path = _DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_rt", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _loop(runner: str, loop_name="knowledge"):
    m = _load("loop_model")
    return m.parse_standard_loop(
        {"id": "k", "skill": "s", "loop_name": loop_name, "automation": {"trigger": "nightly", "runner": runner}},
        skill_name="s",
    )


def test_daemon_runner_calls_orchestrate_with_loop_name():
    r = _load("loop_runner")
    calls = {}
    runner = r.resolve_runner(_loop("daemon"), orchestrate=lambda name, **kw: (calls.setdefault("name", name), "ok")[1])
    result = runner.run(_loop("daemon"))
    assert result == "ok"
    assert calls["name"] == "knowledge"


def test_auto_resolves_to_claude_when_surface_claude_code():
    r = _load("loop_runner")
    runner = r.resolve_runner(_loop("auto"), surface="claude-code")
    assert type(runner).__name__ == "ClaudeRunner"


def test_auto_resolves_to_codex_when_surface_codex():
    r = _load("loop_runner")
    runner = r.resolve_runner(_loop("auto"), surface="codex")
    assert type(runner).__name__ == "CodexRunner"


def test_explicit_codex_runner_selected():
    r = _load("loop_runner")
    runner = r.resolve_runner(_loop("codex"), surface="claude-code")
    assert type(runner).__name__ == "CodexRunner"
