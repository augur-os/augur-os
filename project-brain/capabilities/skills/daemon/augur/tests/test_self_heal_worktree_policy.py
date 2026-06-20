"""Worktree policy tests for the auto-self-heal ops module."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from src.lib.ops_protocol import OpsContext


def _load_self_heal_module():
    # Test lives at project-brain/capabilities/skills/daemon/augur/tests/test_*.py, so parents[2]
    # is the daemon skill root and scripts/ops/self_heal.py is its sibling.
    module_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "ops"
        / "self_heal.py"
    )
    module_name = "_test_self_heal_worktree_policy"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load self_heal module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _ctx(project_root: Path) -> OpsContext:
    return OpsContext(project_root=project_root, config={}, dry_run=False)


def _finding(
    key: str = "worktree-runtime-error",
    severity: str = "high",
    message: str = "dashboard chunk failed",
    file: str = "apps/dashboard/app/page.tsx",
):
    return SimpleNamespace(
        dedup_key=key,
        severity=severity,
        message=message,
        file=file,
    )


def test_worktree_scan_reports_findings_as_validation_only(monkeypatch, tmp_path: Path):
    self_heal = _load_self_heal_module()
    monkeypatch.setattr(self_heal, "_is_inside_worktree", lambda _root: True)
    monkeypatch.setattr(
        self_heal,
        "healer",
        SimpleNamespace(scan_for_errors=lambda: [_finding()]),
    )

    result = self_heal.scan(_ctx(tmp_path))

    assert len(result.issues) == 1
    assert result.issues[0]["entry_key"] == "worktree-runtime-error"
    assert result.issues[0]["worktree_validation_only"] is True
    assert "validation-only worktree mode" in result.summary


def test_worktree_fix_reports_without_mutating(monkeypatch, tmp_path: Path):
    self_heal = _load_self_heal_module()
    fix_calls = []
    fake_healer = SimpleNamespace(
        scan_for_errors=lambda: [],
        fix_entry=lambda entry_key: fix_calls.append(entry_key),
    )
    monkeypatch.setattr(self_heal, "_is_inside_worktree", lambda _root: True)
    monkeypatch.setattr(self_heal, "healer", fake_healer)

    result = self_heal.fix(
        _ctx(tmp_path),
        [{"entry_key": "worktree-runtime-error", "file": "apps/dashboard/app/page.tsx"}],
    )

    assert result.success is True
    assert result.fix_type == "report"
    assert result.changes == []
    assert result.actions == [
        {
            "entry_key": "worktree-runtime-error",
            "skipped": True,
            "reason": "validation-only worktree mode",
        }
    ]
    assert "validation-only" in result.summary
    assert fix_calls == []
