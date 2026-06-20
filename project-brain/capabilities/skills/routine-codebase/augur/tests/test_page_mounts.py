"""Tests for auto-page-mounts scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "page_mounts.py"
_SPEC = importlib.util.spec_from_file_location("page_mounts_under_test", _MODULE_PATH)
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


def test_scan_no_plugins(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert result.items_scanned == 0


def test_scan_detects_missing_page_source(tmp_path: Path) -> None:
    """Custom page declared in SKILL metadata but source file missing."""
    _write(
        _shared_skills(tmp_path) / "browse" / "SKILL.md",
        """---
name: browse
x-augur-hub: workspace
x-augur-config:
  contributions:
    pages:
      - id: details
        page_type: custom
---
Body
""",
    )
    result = mod.scan(_ctx(tmp_path))
    missing = [i for i in result.issues if i["type"] == "missing-page"]
    assert len(missing) == 1


def test_scan_passes_when_page_exists(tmp_path: Path) -> None:
    skill_dir = _shared_skills(tmp_path) / "browse"
    _write(
        skill_dir / "SKILL.md",
        """---
name: browse
x-augur-hub: workspace
x-augur-config:
  contributions:
    pages:
      - id: overview
        page_type: custom
---
Body
""",
    )
    _write(tmp_path / "plugins" / "ui" / "pages" / "workspace" / "browse" / "page.tsx", "export default function Page() {}")
    result = mod.scan(_ctx(tmp_path))
    missing = [i for i in result.issues if i["type"] == "missing-page"]
    assert missing == []
    assert result.items_scanned == 1


def test_scan_detects_invalid_block_type(tmp_path: Path) -> None:
    """Block with non-canonical type is flagged."""
    _write(
        _shared_skills(tmp_path) / "browse" / "SKILL.md",
        """---
name: browse
x-augur-hub: workspace
x-augur-config:
  contributions:
    blocks:
      - id: test:block
        type: custom-widget
---
Body
""",
    )
    result = mod.scan(_ctx(tmp_path))
    bad_type = [i for i in result.issues if i["type"] == "block-invalid-type"]
    assert len(bad_type) == 1


def test_scan_accepts_auto_page_without_custom_source(tmp_path: Path) -> None:
    _write(
        tmp_path / ".claude" / "skills" / "browse" / "SKILL.md",
        """---
name: browse
x-augur-hub: workspace
x-augur-config:
  contributions:
    pages:
      - id: overview
        page_type: auto
---
Body
""",
    )
    result = mod.scan(_ctx(tmp_path))
    missing = [i for i in result.issues if i["type"] == "missing-page"]
    assert missing == []
