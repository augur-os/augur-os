"""Tests for auto-plugin-lint scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "plugin_lint.py"
_SPEC = importlib.util.spec_from_file_location("plugin_lint_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-plugin-lint"


def test_scan_no_plugins(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert result.items_scanned == 0


def test_scan_detects_hub_misalignment(tmp_path: Path) -> None:
    """Plugin in bundle X but x-augur-hub Y is flagged."""
    _write(
        tmp_path / "plugins" / "brain" / "skills" / "browse" / "SKILL.md",
        """---
name: browse
x-augur-hub: life
x-augur-config:
  contributions: {}
---
Body
""",
    )
    result = mod.scan(_ctx(tmp_path))
    hub_issues = [i for i in result.issues if i["pattern"] == "hub-misalignment"]
    assert len(hub_issues) == 1


def test_scan_detects_invalid_block_type(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "browse" / "SKILL.md",
        """---
name: browse
x-augur-hub: workspace
x-augur-config:
  contributions:
    blocks:
      - id: test:block
        type: magic-widget
---
Body
""",
    )
    result = mod.scan(_ctx(tmp_path))
    block_issues = [i for i in result.issues if i["pattern"] == "invalid-block-type"]
    assert len(block_issues) == 1


def test_scan_all_pass(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "browse" / "SKILL.md",
        """---
name: browse
x-augur-hub: workspace
x-augur-config-file: config.yaml
---
Body
""",
    )
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "browse" / "config.yaml",
        """contributions:
  blocks:
    - id: test:block
      type: tabbed
""",
    )
    result = mod.scan(_ctx(tmp_path))
    assert result.issues == []
    assert "all plugins pass" in result.summary
    assert result.items_scanned == 1


def test_normalize_issue_uses_message_when_detail_missing(tmp_path: Path) -> None:
    target = tmp_path / "plugins" / "demo.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("demo: true\n")

    normalized = mod._normalize_issue(  # noqa: SLF001
        tmp_path,
        {"file": "plugins/demo.yaml", "message": "scanner message only"},
    )

    assert normalized == ("plugins/demo.yaml", "scanner message only")


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"pattern": "hub-misalignment"}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary


def test_declares_windows_report_only_capabilities() -> None:
    assert mod.OPS_CAPABILITIES.platforms == ("cross_platform",)
    assert mod.OPS_CAPABILITIES.windows_fix_mode == "report_only"
