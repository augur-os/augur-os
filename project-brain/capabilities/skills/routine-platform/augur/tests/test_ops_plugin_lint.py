"""Unit tests for auto-plugin-lint ops command."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

# Setup import path for routine-platform scripts and src/lib imports.
SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
SRC_DIR = str(PROJECT_ROOT / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Direct file import to avoid namespace collision with other ops packages
# which gets cached in sys.modules during full-suite pytest collection.
_spec = importlib.util.spec_from_file_location(
    "ops.plugin_lint",
    SCRIPTS_DIR / "plugin_lint.py",
    submodule_search_locations=[],
)
plugin_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin_lint)

from src.lib.ops_protocol import OpsContext


def _ctx(project_root: Path, config: dict | None = None) -> OpsContext:
    return OpsContext(project_root=project_root, config=config or {})


def test_normalize_issue_accepts_repo_relative_file(tmp_path: Path):
    target = tmp_path / "plugins" / "test" / "skills" / "demo" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("---\nname: demo\ndescription: Demo\n---\n")

    normalized = plugin_lint._normalize_issue(  # noqa: SLF001
        tmp_path,
        {"file": "skills/demo/SKILL.md", "detail": "missing field"},
    )
    assert normalized == ("skills/demo/SKILL.md", "missing field")


def test_normalize_issue_rejects_path_outside_repo(tmp_path: Path):
    outside = Path("/tmp/outside.yaml")
    normalized = plugin_lint._normalize_issue(  # noqa: SLF001
        tmp_path,
        {"file": str(outside), "detail": "bad"},
    )
    assert normalized is None


def test_fix_skips_invalid_payload_and_respects_issue_limit(
    tmp_path: Path,
    monkeypatch,
):
    target_a = tmp_path / "plugins" / "a.yaml"
    target_b = tmp_path / "plugins" / "b.yaml"
    target_a.parent.mkdir(parents=True)
    target_a.write_text("a: 1\n")
    target_b.write_text("b: 1\n")

    monkeypatch.setattr(plugin_lint, "_find_cli", lambda: "claude")

    status_sequence = iter([
        {},
        {"plugins/a.yaml": " M"},
    ])
    monkeypatch.setattr(plugin_lint, "_git_status_map", lambda _root: next(status_sequence))
    monkeypatch.setattr(plugin_lint, "_restore_paths", lambda *_args, **_kwargs: None)

    monkeypatch.setattr(
        plugin_lint.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout="fixed", stderr=""),
    )

    issues = [
        {"file": "", "detail": "invalid"},
        {"file": "plugins/a.yaml", "detail": "fix a"},
        {"file": "plugins/b.yaml", "detail": "fix b"},
    ]
    result = plugin_lint.fix(
        _ctx(tmp_path, {"max_issues_per_run": 1, "strict_file_scope": True}),
        issues,
    )

    assert result.success is True
    assert result.changes == ["plugins/a.yaml"]
    assert any(a.get("reason") == "invalid-issue-payload" for a in result.actions)
    fixed_actions = [a for a in result.actions if a.get("status") == "fixed"]
    assert len(fixed_actions) == 1
    assert fixed_actions[0]["file"] == "plugins/a.yaml"


def test_fix_fails_and_restores_on_scope_violation(tmp_path: Path, monkeypatch):
    target = tmp_path / "plugins" / "target.yaml"
    other = tmp_path / "plugins" / "other.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("x: 1\n")
    other.write_text("y: 1\n")

    monkeypatch.setattr(plugin_lint, "_find_cli", lambda: "claude")
    status_sequence = iter([
        {},
        {"plugins/target.yaml": " M", "plugins/other.yaml": " M"},
    ])
    monkeypatch.setattr(plugin_lint, "_git_status_map", lambda _root: next(status_sequence))

    restored = {}

    def _capture_restore(_root, paths, _untracked):
        restored["paths"] = paths

    monkeypatch.setattr(plugin_lint, "_restore_paths", _capture_restore)
    monkeypatch.setattr(
        plugin_lint.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr=""),
    )

    result = plugin_lint.fix(
        _ctx(tmp_path, {"strict_file_scope": True}),
        [{"file": "plugins/target.yaml", "detail": "fix target"}],
    )

    # No changes produced -> report-only (success=True, fix_type="report")
    # so the engine doesn't penalize trust for environment/CLI issues.
    assert result.success is True
    assert result.fix_type == "report"
    assert result.changes == []
    assert restored["paths"] == ["plugins/other.yaml"]
    failure = next(a for a in result.actions if a.get("status") == "failed")
    assert failure["reason"] == "scope-violation"


def test_scan_hub_alignment_passes_for_matching_bundle(tmp_path: Path):
    """A plugin whose contributes_to matches its bundle produces no findings."""
    skill_dir = tmp_path / "plugins" / "admin" / "skills" / "channels"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: channels\ndescription: Channels\nx-augur-hub: admin\n---\n"
    )

    result = plugin_lint.scan(_ctx(tmp_path))

    assert result.issues == []
    assert result.severity == "info"


def test_scan_hub_alignment_flags_misaligned_plugin(tmp_path: Path):
    """A plugin whose contributes_to differs from its bundle is flagged HIGH."""
    skill_dir = tmp_path / "plugins" / "ai" / "skills" / "page-builder"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: page-builder\ndescription: Builder\nx-augur-hub: admin\n---\n"
    )

    result = plugin_lint.scan(_ctx(tmp_path))

    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue["severity"] == "high"
    assert issue["pattern"] == "hub-misalignment"
    assert "page-builder" in issue["message"]
    assert "skills/page-builder/" in issue["message"]
    assert result.severity == "warning"


def test_scan_hub_alignment_skips_missing_contributes_to(tmp_path: Path):
    """A plugin without contributes_to is not flagged (other checks may catch it)."""
    skill_dir = tmp_path / "plugins" / "dev" / "skills" / "toolbox"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: toolbox\ndescription: Toolbox\n---\n")

    result = plugin_lint.scan(_ctx(tmp_path))

    assert result.issues == []


def test_fix_records_claude_nonzero_exit(tmp_path: Path, monkeypatch):
    target = tmp_path / "plugins" / "target.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("x: 1\n")

    monkeypatch.setattr(plugin_lint, "_find_cli", lambda: "claude")
    status_sequence = iter([{}, {}])
    monkeypatch.setattr(plugin_lint, "_git_status_map", lambda _root: next(status_sequence))
    monkeypatch.setattr(plugin_lint, "_restore_paths", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        plugin_lint.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=2, stdout="", stderr="boom"),
    )

    result = plugin_lint.fix(
        _ctx(tmp_path, {"strict_file_scope": True}),
        [{"file": "plugins/target.yaml", "detail": "fix target"}],
    )

    # No changes produced -> report-only (success=True, fix_type="report")
    # so the engine doesn't penalize trust for CLI failures.
    assert result.success is True
    assert result.fix_type == "report"
    assert result.changes == []
    failure = next(a for a in result.actions if a.get("status") == "failed")
    assert failure["reason"] == "claude-exit"
    assert failure["exit"] == 2
