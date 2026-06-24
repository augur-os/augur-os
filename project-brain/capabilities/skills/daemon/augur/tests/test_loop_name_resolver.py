"""Pure resolver: the loop name is the command."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_MOD = _REPO / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "routine_orchestrator" / "loop_name_resolver.py"


def _load():
    spec = importlib.util.spec_from_file_location("loop_name_resolver_uut", _MOD)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m); return m


_KW = dict(
    verbs={"list", "status", "run", "report", "schedule", "goal", "scan-only", "orchestrate"},
    prompt_loops={"inbox-triage", "dream"},
    orchestrator_loops={"hardening", "code-quality", "testing"},
    goals={"harden", "clean", "harden-and-clean"},
)


def test_known_verb_passes_through():
    d = _load().resolve_loop_token("run", **_KW)
    assert d.kind == "verb" and d.argv is None


def test_prompt_loop_routes_to_run():
    d = _load().resolve_loop_token("inbox-triage", **_KW)
    assert d.kind == "prompt"
    assert d.argv == ["run", "inbox-triage"]


def test_orchestrator_loop_routes_to_single_loop_goal():
    d = _load().resolve_loop_token("hardening", **_KW)
    assert d.kind == "orchestrator"
    assert d.argv == ["goal", "hardening", "--catalog-loop"]


def test_catalog_goal_routes_to_catalog_loop():
    d = _load().resolve_loop_token("harden", **_KW)
    assert d.kind == "goal"
    assert d.argv == ["goal", "harden", "--catalog-loop"]


def test_verb_beats_same_named_loop():
    # precedence: a token that is BOTH a verb and a loop resolves as the verb
    d = _load().resolve_loop_token("status", **{**_KW, "prompt_loops": {"status", "inbox-triage"}})
    assert d.kind == "verb"


def test_unknown_token_is_friendly():
    d = _load().resolve_loop_token("hardenning", **_KW)  # typo
    assert d.kind == "unknown"
    assert d.argv is None
    assert "hardening" in d.message  # did-you-mean suggests the close real name
    assert "did you mean" in d.message.lower() or "unknown loop" in d.message.lower()
