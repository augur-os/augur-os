"""Tests for auto-dead-wiring scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dead_wiring_ops.py"
_SPEC = importlib.util.spec_from_file_location("dead_wiring_ops_under_test", _MODULE_PATH)
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


def test_scan_no_yamls(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []


def test_scan_d0_surface_counts(tmp_path: Path) -> None:
    """d0 just counts declarations without validating."""
    _write(
        _shared_skills(tmp_path) / "browse" / "SKILL.md",
        """---
name: browse
x-augur-hub: adaptive
x-augur-config:
  contributions:
    pages:
      - id: overview
    blocks:
      - id: test:block
---
Body
""",
    )
    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert result.issues == []
    assert "1 pages" in result.summary


def test_scan_d1_detects_missing_page(tmp_path: Path) -> None:
    """d1 flags pages declared in SKILL.md but without page.tsx."""
    _write(
        _shared_skills(tmp_path) / "browse" / "SKILL.md",
        """---
name: browse
x-augur-hub: adaptive
x-augur-config:
  contributions:
    pages:
      - id: nonexistent-page
---
Body
""",
    )
    result = mod.scan(_ctx(tmp_path, difficulty=1))
    missing = [i for i in result.issues if i["type"] == "missing_page"]
    assert len(missing) == 1


def test_scan_d1_no_issue_when_page_exists(tmp_path: Path) -> None:
    """d1 passes when the declared page has a page.tsx file."""
    skill_dir = _shared_skills(tmp_path) / "browse"
    _write(
        skill_dir / "SKILL.md",
        """---
name: browse
x-augur-hub: adaptive
x-augur-config:
  contributions:
    pages:
      - id: overview
---
Body
""",
    )
    _write(skill_dir / "augur" / "dashboard" / "page.tsx", "export default function Page() {}")
    result = mod.scan(_ctx(tmp_path, difficulty=1))
    missing = [i for i in result.issues if i["type"] == "missing_page"]
    assert missing == []


def test_fix_returns_report_only(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"type": "missing_page"}])
    assert result.success is True
