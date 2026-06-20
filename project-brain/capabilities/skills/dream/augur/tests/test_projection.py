"""Tests for cross-client routine projection metadata (ADR-744 task 13)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "projection.py"
_SPEC = importlib.util.spec_from_file_location("dream_projection", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_codex_seed_path_resolves_to_a_real_yaml():
    path = mod.dream_codex_seed_path()
    assert path.is_file(), f"expected seed yaml at {path}"
    assert path.name == "routine-schedule.yaml"
    assert "codex-dream-schedules.yaml" not in str(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    # The dream Codex schedule binding was intentionally removed (commit
    # 36d9da038): the dream cycle is now scheduled via Claude /schedule remote
    # rather than Codex. The seed still resolves to the canonical
    # routine-schedule.yaml and exposes a `schedules` list (now empty).
    assert isinstance(data.get("schedules", []), list)


def test_routine_doc_path_resolves_to_dream_md():
    path = mod.dream_routine_doc_path()
    assert path.is_file()
    assert path.name == "dream.md"
    body = path.read_text(encoding="utf-8")
    # Every phase listed in the routine must be present
    for phase in (
        "## Phase 0", "## Phase 1", "## Phase 2", "## Phase 3", "## Phase 4",
        "## Phase 5", "## Phase 6", "## Phase 7", "## Phase 8", "## Phase 9",
    ):
        assert phase in body


def test_manual_command_template_for_graceful_degradation():
    """Cursor / Copilot get a static manual-run template."""
    template = mod.dream_manual_command_template()
    assert "/dream" in template
    assert template.strip().endswith("the phases.")


def test_activation_hint_distinguishes_clients():
    codex = mod.dream_activation_hint("codex")
    claude = mod.dream_activation_hint("claude-code")
    cursor = mod.dream_activation_hint("cursor")
    assert "auto-scheduled" in codex
    assert "/schedule /dream" in claude
    assert "manually" in cursor


def test_activation_hint_falls_back_for_unknown_clients():
    """An unrecognized client_id must NOT raise — graceful degradation."""
    hint = mod.dream_activation_hint("some-future-client")
    assert "some-future-client" in hint
