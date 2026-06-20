"""Tests for auto-frontmatter-lint scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "frontmatter_lint.py"
_SPEC = importlib.util.spec_from_file_location("frontmatter_lint_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def _shared_skills(tmp_path: Path) -> Path:
    return tmp_path / "project-brain" / "capabilities" / "skills"


def test_scan_d0_no_adrs(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert isinstance(result, ScanResult)
    assert result.issues == []


def test_scan_d0_valid_adr(tmp_path: Path) -> None:
    """ADR with proper frontmatter passes."""
    _write(tmp_path / "docs" / "decisions" / "ADR-001.md", "---\ntitle: Test\n---\nContent\n")
    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert result.issues == []


def test_scan_d0_adr_missing_frontmatter(tmp_path: Path) -> None:
    """ADR without frontmatter is flagged."""
    _write(tmp_path / "docs" / "decisions" / "ADR-001.md", "# ADR 001\nNo frontmatter here.\n")
    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert len(result.issues) == 1
    assert result.issues[0]["action"] == "missing-frontmatter"
    assert result.severity == "error"


def test_scan_d1_stale_yaml_actions(tmp_path: Path) -> None:
    """d1 flags .yaml action files that should be .md."""
    _write(
        _shared_skills(tmp_path) / "browse" / "assets" / "actions" / "test.yaml",
        "id: test\ndispatch: fire\n",
    )
    result = mod.scan(_ctx(tmp_path, difficulty=1))
    stale = [i for i in result.issues if i["action"] == "stale-yaml-action"]
    assert len(stale) == 1
    assert stale[0]["kind"] == "actionable"
    assert stale[0]["finding_band"] == "mechanical"
    assert stale[0]["path_fix"] is True


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"action": "missing-frontmatter"}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary


def test_fix_reports_yaml_and_md_paths_for_migration(tmp_path: Path) -> None:
    yaml_path = _shared_skills(tmp_path) / "browse" / "assets" / "actions" / "test.yaml"
    _write(yaml_path, "id: test\ndispatch: fire\n")
    issue = {
        "action": "stale-yaml-action",
        "file": "project-brain/capabilities/skills/browse/assets/actions/test.yaml",
    }

    result = mod.fix(_ctx(tmp_path, difficulty=2), [issue])

    assert result.success is True
    assert not yaml_path.exists()
    assert yaml_path.with_suffix(".md").is_file()
    assert "project-brain/capabilities/skills/browse/assets/actions/test.yaml" in result.changes
    assert "project-brain/capabilities/skills/browse/assets/actions/test.md" in result.changes
    assert not any(change.startswith("docs/generated/") for change in result.changes)
