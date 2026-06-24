"""Argv pre-processor: builds known sets from the registry and rewrites bare names."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_MOD = _REPO / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "mcp" / "__init__.py"


def _load():
    scripts = _MOD.parent.parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("daemon_mcp_argv", _MOD)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m); return m


def test_verb_unchanged():
    m = _load()
    out, err = m._rewrite_loop_argv(["list"])
    assert out == ["list"] and err is None


def test_empty_unchanged():
    m = _load()
    out, err = m._rewrite_loop_argv([])
    assert out == [] and err is None


def test_known_loop_is_rewritten():
    m = _load()
    # 'inbox-triage' is a real registered loop; it must rewrite to a run/goal route, not stay bare
    out, err = m._rewrite_loop_argv(["inbox-triage"])
    assert err is None
    assert out[0] in {"run", "goal"} and "inbox-triage" in out


def test_unknown_returns_friendly_error():
    m = _load()
    out, err = m._rewrite_loop_argv(["definitely-not-a-loop"])
    assert err is not None and "unknown loop or goal" in err
