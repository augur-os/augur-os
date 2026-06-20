"""Tests for auto-page-mounts ops module."""
from __future__ import annotations

from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_test_ctx


def _ctx(tmp_path: Path, **kwargs) -> OpsContext:
    return make_test_ctx(tmp_path, **kwargs)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestScan:
    def test_scan_no_plugins_dir_returns_clean(self, tmp_path: Path):
        from skills.daemon.scripts.ops import page_mounts

        result = page_mounts.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert result.issues == []
        assert "surface only" in result.summary.lower() or "skill directories checked" in result.summary.lower()

    def test_scan_d0_surface_check_only(self, tmp_path: Path):
        from skills.daemon.scripts.ops import page_mounts

        (tmp_path / "project-brain" / "capabilities" / "skills").mkdir(parents=True)
        result = page_mounts.scan(_ctx(tmp_path, difficulty=0))

        assert result.issues == []
        assert result.health == "verified"
        assert "surface only" in result.summary.lower() or "d0" in result.summary.lower()

    def test_scan_d1_detects_missing_page_source(self, tmp_path: Path):
        from skills.daemon.scripts.ops import page_mounts

        skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "demo"
        _write(
            skill_dir / "SKILL.md",
            "---\n"
            "name: demo\n"
            "description: Demo\n"
            "x-augur-hub: test\n"
            "x-augur-config:\n"
            "  contributions:\n"
            "    pages:\n"
            "      - id: overview\n"
            "        file: dashboard/overview/page.tsx\n"
            "---\n",
        )
        # Note: not creating the actual page file to trigger the missing detection

        result = page_mounts.scan(_ctx(tmp_path, difficulty=1))

        assert len(result.issues) == 1
        assert "missing" in result.issues[0]["detail"].lower()
        assert result.severity == "warning"

    def test_scan_d1_passes_when_page_source_exists(self, tmp_path: Path):
        from skills.daemon.scripts.ops import page_mounts

        skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "demo"
        _write(
            skill_dir / "SKILL.md",
            "---\n"
            "name: demo\n"
            "description: Demo\n"
            "x-augur-hub: test\n"
            "x-augur-config:\n"
            "  contributions:\n"
            "    pages:\n"
            "      - id: overview\n"
            "        file: dashboard/overview/page.tsx\n"
            "---\n",
        )
        _write(skill_dir / "dashboard" / "overview" / "page.tsx", "export default function Page() {}")

        result = page_mounts.scan(_ctx(tmp_path, difficulty=1))

        assert result.issues == []
        assert result.severity == "info"

    def test_scan_handles_invalid_frontmatter_gracefully(self, tmp_path: Path):
        from skills.daemon.scripts.ops import page_mounts

        skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "broken"
        _write(skill_dir / "SKILL.md", "---\ninvalid: [yaml\n")

        result = page_mounts.scan(_ctx(tmp_path, difficulty=1))

        assert isinstance(result, ScanResult)


class TestFix:
    def test_fix_dry_run(self, tmp_path: Path):
        from skills.daemon.scripts.ops import page_mounts

        result = page_mounts.fix(
            _ctx(tmp_path, dry_run=True),
            [{"action": "missing-page-overview", "file": "test.tsx", "detail": "missing"}],
        )

        assert isinstance(result, FixResult)
        assert result.success is True
        assert "Dry run" in result.summary

    def test_fix_no_issues(self, tmp_path: Path):
        from skills.daemon.scripts.ops import page_mounts

        result = page_mounts.fix(_ctx(tmp_path), [])

        assert result.success is True
        assert "No issues" in result.summary

    def test_fix_writes_report(self, tmp_path: Path):
        from skills.daemon.scripts.ops import page_mounts

        issues = [
            {"action": "missing-page-overview", "file": "test/page.tsx",
             "detail": "Page source missing: dashboard/overview/page.tsx"},
        ]
        result = page_mounts.fix(_ctx(tmp_path), issues)

        assert result.success is True
        assert result.fix_type == "report"
        report_dir = tmp_path / "docs" / "generated" / "hardening"
        assert report_dir.exists()


class TestModuleInterface:
    def test_has_name(self):
        from skills.daemon.scripts.ops import page_mounts
        assert page_mounts.name == "auto-page-mounts"

    def test_declares_windows_report_only_capabilities(self):
        from skills.daemon.scripts.ops import page_mounts
        assert page_mounts.OPS_CAPABILITIES.platforms == ("cross_platform",)
        assert page_mounts.OPS_CAPABILITIES.windows_fix_mode == "report_only"

    def test_has_scan_callable(self):
        from skills.daemon.scripts.ops import page_mounts
        assert callable(page_mounts.scan)

    def test_has_fix_callable(self):
        from skills.daemon.scripts.ops import page_mounts
        assert callable(page_mounts.fix)
