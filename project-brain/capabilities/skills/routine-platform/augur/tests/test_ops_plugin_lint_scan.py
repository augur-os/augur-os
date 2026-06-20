"""Tests for auto-plugin-lint ops module scan() function."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_test_ctx

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists() and (
            (parent / "skills").exists()
            or (parent / "project-brain" / "capabilities" / "skills").exists()
        ):
            return parent
    raise RuntimeError("Project root not found")


PROJECT_ROOT = _find_project_root()
SRC_DIR = str(PROJECT_ROOT / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

_spec = importlib.util.spec_from_file_location(
    "ops.plugin_lint",
    SCRIPTS_DIR / "plugin_lint.py",
    submodule_search_locations=[],
)
plugin_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin_lint)


def _ctx(tmp_path: Path, **kwargs) -> OpsContext:
    return make_test_ctx(tmp_path, **kwargs)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestScan:
    def test_scan_no_plugins_dir_returns_clean(self, tmp_path: Path):
        result = plugin_lint.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert result.issues == []
        assert result.severity == "info"

    def test_scan_empty_plugins_dir(self, tmp_path: Path):
        (tmp_path / "plugins").mkdir()
        result = plugin_lint.scan(_ctx(tmp_path))

        assert result.issues == []
        assert "all plugins pass" in result.summary

    def test_scan_detects_hub_misalignment(self, tmp_path: Path):
        skill_dir = tmp_path / "plugins" / "dev" / "skills" / "my-tool"
        _write(
            skill_dir / "SKILL.md",
            "---\nname: my-tool\ndescription: Tool\nx-augur-hub: admin\n---\n",
        )

        result = plugin_lint.scan(_ctx(tmp_path))

        assert len(result.issues) == 1
        assert result.issues[0]["pattern"] == "hub-misalignment"
        assert "admin" in result.issues[0]["message"]
        assert "dev" in result.issues[0]["message"]
        assert result.severity == "warning"

    def test_scan_aligned_plugin_passes(self, tmp_path: Path):
        skill_dir = tmp_path / "plugins" / "dev" / "skills" / "my-tool"
        _write(
            skill_dir / "SKILL.md",
            "---\nname: my-tool\ndescription: Tool\nx-augur-hub: dev\n---\n",
        )

        result = plugin_lint.scan(_ctx(tmp_path))

        assert result.issues == []

    def test_scan_skips_skills_without_contributes_to(self, tmp_path: Path):
        skill_dir = tmp_path / "plugins" / "dev" / "skills" / "legacy"
        _write(
            skill_dir / "SKILL.md",
            "---\nname: legacy\ndescription: no hub\n---\n",
        )

        result = plugin_lint.scan(_ctx(tmp_path))

        assert result.issues == []

    def test_scan_handles_invalid_frontmatter(self, tmp_path: Path):
        skill_dir = tmp_path / "plugins" / "dev" / "skills" / "broken"
        _write(skill_dir / "SKILL.md", "---\ninvalid: [yaml\n")

        result = plugin_lint.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)


class TestFix:
    def test_fix_dry_run(self, tmp_path: Path):
        result = plugin_lint.fix(
            _ctx(tmp_path, dry_run=True),
            [{"detail": "test issue", "file": "test.py"}],
        )

        assert isinstance(result, FixResult)
        assert result.success is True
        assert "Dry run" in result.summary

    def test_fix_no_issues(self, tmp_path: Path):
        result = plugin_lint.fix(_ctx(tmp_path), [])

        assert result.success is True
        assert "No plugin lint issues" in result.summary


class TestModuleInterface:
    def test_has_name(self):
        assert plugin_lint.name == "auto-plugin-lint"

    def test_has_scan_callable(self):
        assert callable(plugin_lint.scan)

    def test_has_fix_callable(self):
        assert callable(plugin_lint.fix)
