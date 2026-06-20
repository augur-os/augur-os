"""Tests for auto-api-health ops module."""
from __future__ import annotations

from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_test_ctx


def _ctx(tmp_path: Path, **kwargs) -> OpsContext:
    return make_test_ctx(tmp_path, **kwargs)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestScan:
    """auto-api-health has no autonomous scanner -- scan always returns empty."""

    def test_scan_returns_empty_scan_result(self, tmp_path: Path):
        from skills.daemon.scripts.ops import api_health

        result = api_health.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert result.issues == []
        assert result.severity == "info"
        assert "no autonomous scanner" in result.summary

    def test_scan_at_various_difficulties(self, tmp_path: Path):
        from skills.daemon.scripts.ops import api_health

        for d in range(5):
            result = api_health.scan(_ctx(tmp_path, difficulty=d))
            assert result.issues == []


class TestFix:
    def test_fix_dry_run(self, tmp_path: Path):
        from skills.daemon.scripts.ops import api_health

        result = api_health.fix(
            _ctx(tmp_path, dry_run=True),
            [{"action": "api-route-fail", "detail": "500 error", "file": "n/a"}],
        )

        assert isinstance(result, FixResult)
        assert result.success is True
        assert "Dry run" in result.summary

    def test_fix_no_issues(self, tmp_path: Path):
        from skills.daemon.scripts.ops import api_health

        result = api_health.fix(_ctx(tmp_path), [])

        assert result.success is True
        assert "No API health issues" in result.summary

    def test_fix_writes_hardening_report(self, tmp_path: Path):
        from skills.daemon.scripts.ops import api_health

        issues = [
            {"action": "api-fail", "detail": "/api/test returns 500", "file": "n/a"},
        ]
        result = api_health.fix(_ctx(tmp_path), issues)

        assert result.success is True
        report_dir = tmp_path / "docs" / "generated" / "hardening"
        assert report_dir.exists()
        report_files = list(report_dir.glob("hardening-*.md"))
        assert len(report_files) == 1
        content = report_files[0].read_text()
        assert "api-route-health" in content

    def test_fix_adds_todo_bug_to_source_file(self, tmp_path: Path):
        from skills.daemon.scripts.ops import api_health

        source_file = tmp_path / "apps" / "dashboard" / "app" / "api" / "test" / "route.ts"
        _write(source_file, 'export function GET() { return Response.json({}); }\n')

        issues = [
            {
                "action": "api-fail",
                "detail": "/api/test returns 500",
                "file": "apps/dashboard/app/api/test/route.ts",
            },
        ]
        result = api_health.fix(_ctx(tmp_path), issues)

        assert result.success is True
        updated = source_file.read_text()
        assert "TODO_BUG" in updated

    def test_fix_does_not_duplicate_todo_bug(self, tmp_path: Path):
        from skills.daemon.scripts.ops import api_health

        source_file = tmp_path / "apps" / "test.ts"
        _write(
            source_file,
            "# TODO_BUG: API route health failure — see hardening report\n"
            "export function GET() {}\n",
        )

        issues = [
            {"action": "api-fail", "detail": "fail", "file": "apps/test.ts"},
        ]
        api_health.fix(_ctx(tmp_path), issues)

        content = source_file.read_text()
        assert content.count("TODO_BUG") == 1


class TestModuleInterface:
    def test_has_name(self):
        from skills.daemon.scripts.ops import api_health
        assert api_health.name == "auto-api-health"

    def test_has_scan_callable(self):
        from skills.daemon.scripts.ops import api_health
        assert callable(api_health.scan)

    def test_has_fix_callable(self):
        from skills.daemon.scripts.ops import api_health
        assert callable(api_health.fix)
