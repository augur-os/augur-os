"""Tests for the Codex adapter's _sync_dream_automations transition shim.

ADR-758 moved dream automation projection to the unified routine registry.
The legacy dream method remains only as a deprecated alias-period shim.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Repo root is discovered by marker (pyproject.toml + .git), robust to brain-layout
# depth; parents[2] is the ai skill root. sync_agents under scripts/ is the target.
PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_ADAPTER_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(_ADAPTER_DIR))

from sync_agents.adapters import codex as codex_adapter  # noqa: E402


def test_sync_dream_automations_delegates_to_routine_projection(monkeypatch):
    """The deprecated dream shim delegates to the unified routine projector."""
    calls: list[dict[str, object]] = []

    def fake_sync(**kwargs):
        calls.append(kwargs)

    adapter = codex_adapter.CodexAdapter()
    monkeypatch.setattr(adapter, "_sync_routine_automations", fake_sync)
    adapter._sync_dream_automations()

    assert calls == [
        {"routine_ids": {"dream"}, "label": "dream", "prune": False}
    ]


def test_sync_dream_automations_no_longer_depends_on_legacy_seed_path(
    monkeypatch, tmp_path
):
    """The deprecated shim does not inspect the old dream seed path directly."""
    monkeypatch.setattr(
        codex_adapter,
        "get_project_brain_skills_dir",
        lambda _root: tmp_path,
    )
    calls: list[dict[str, object]] = []

    def fake_sync(**kwargs):
        calls.append(kwargs)

    adapter = codex_adapter.CodexAdapter()
    monkeypatch.setattr(adapter, "_sync_routine_automations", fake_sync)
    adapter._sync_dream_automations()

    assert calls == [
        {"routine_ids": {"dream"}, "label": "dream", "prune": False}
    ]
