"""Tests for auto-debt-scan ops module."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_test_ctx

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_ops_module(module_name: str):
    module_path = SCRIPTS_DIR / "ops" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"_platform_admin_ops_{module_name}",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


debt_scan = _load_ops_module("debt_scan")


def _ctx(tmp_path: Path, **kwargs) -> OpsContext:
    return make_test_ctx(tmp_path, **kwargs)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestScan:
    def test_scan_d0_returns_no_issues(self, tmp_path: Path):
        """d0 does not scan for large files or git churn."""

        result = debt_scan.scan(_ctx(tmp_path, difficulty=0))

        assert isinstance(result, ScanResult)
        assert result.issues == []
        assert result.severity == "info"

    def test_scan_d1_detects_large_files(self, tmp_path: Path):
        large_file = tmp_path / "src" / "big_module.py"
        _write(large_file, "\n".join(f"line {i}" for i in range(600)))

        result = debt_scan.scan(_ctx(tmp_path, difficulty=1))

        large_issues = [i for i in result.issues if i["action"] == "large-file"]
        assert len(large_issues) == 1
        assert large_issues[0]["lines"] == 600
        assert result.severity == "warning"

    def test_scan_d1_ignores_files_under_threshold(self, tmp_path: Path):
        small_file = tmp_path / "src" / "small.py"
        _write(small_file, "\n".join(f"line {i}" for i in range(100)))

        result = debt_scan.scan(_ctx(tmp_path, difficulty=1))

        large_issues = [i for i in result.issues if i["action"] == "large-file"]
        assert len(large_issues) == 0

    def test_scan_d1_skips_node_modules(self, tmp_path: Path):
        big = tmp_path / "node_modules" / "lib" / "huge.ts"
        _write(big, "\n".join(f"line {i}" for i in range(1000)))

        result = debt_scan.scan(_ctx(tmp_path, difficulty=1))

        assert result.issues == []

    def test_scan_d1_skips_generated_files(self, tmp_path: Path):
        gen = tmp_path / "src" / "generated-block-registry.ts"
        _write(gen, "\n".join(f"line {i}" for i in range(1000)))

        result = debt_scan.scan(_ctx(tmp_path, difficulty=1))

        assert result.issues == []

    @patch("subprocess.run")
    def test_scan_d2_detects_git_churn(self, mock_run: MagicMock, tmp_path: Path):
        # Mock git log output showing high churn
        git_output = "\n".join(["src/hot_file.py"] * 10 + ["src/cold_file.py"] * 1)
        mock_run.return_value = MagicMock(returncode=0, stdout=git_output, stderr="")

        result = debt_scan.scan(_ctx(tmp_path, difficulty=2))

        churn_issues = [i for i in result.issues if i["action"] == "high-churn"]
        assert len(churn_issues) == 1
        assert churn_issues[0]["file"] == "src/hot_file.py"
        assert churn_issues[0]["changes_in_last_50"] == 10

    def test_scan_empty_project(self, tmp_path: Path):
        result = debt_scan.scan(_ctx(tmp_path, difficulty=1))

        assert result.issues == []
        assert result.severity == "info"


class TestFix:
    def test_fix_dry_run(self, tmp_path: Path):
        result = debt_scan.fix(
            _ctx(tmp_path, dry_run=True),
            [{"action": "large-file", "file": "x.py", "lines": 600, "threshold": 450}],
        )

        assert isinstance(result, FixResult)
        assert result.success is True
        assert "Dry run" in result.summary

    def test_fix_generates_debt_report(self, tmp_path: Path):
        issues = [
            {"action": "large-file", "file": "src/big.py", "lines": 700, "threshold": 450},
            {"action": "high-churn", "file": "src/hot.py", "changes_in_last_50": 8},
        ]
        result = debt_scan.fix(_ctx(tmp_path), issues)

        assert result.success is True
        assert result.fix_type == "report"
        report_file = tmp_path / "docs" / "generated" / "tech-debt-report.md"
        assert report_file.exists()
        content = report_file.read_text()
        assert "Oversized Files" in content
        assert "High Churn" in content
        assert "src/big.py" in content
        assert "src/hot.py" in content

    def test_fix_does_not_duplicate_typescript_cleanup_marker(self, tmp_path: Path):
        target = tmp_path / "src" / "big.ts"
        _write(
            target,
            "\n".join(
                [
                    "// TODO_CLEANUP: This file is 900 lines — consider splitting into smaller modules",
                    *[f"line {i}" for i in range(900)],
                ]
            ),
        )

        issues = [
            {"action": "large-file", "file": "src/big.ts", "lines": 901, "threshold": 450},
        ]
        result = debt_scan.fix(_ctx(tmp_path, difficulty=1), issues)

        assert result.success is True
        content = target.read_text(encoding="utf-8")
        assert content.count("TODO_CLEANUP: This file is") == 1

    def test_fix_prunes_stale_cleanup_markers(self, tmp_path: Path):
        target = tmp_path / "src" / "former_big.ts"
        _write(
            target,
            "\n".join(
                [
                    "// TODO_CLEANUP: This file is 900 lines — consider splitting into smaller modules",
                    *[f"line {i}" for i in range(50)],
                ]
            ),
        )

        result = debt_scan.fix(_ctx(tmp_path, difficulty=1), [])

        assert result.success is True
        assert "stale markers removed" in result.summary
        assert "TODO_CLEANUP: This file is" not in target.read_text(encoding="utf-8")

    def test_fix_inserts_python_marker_after_future_import(self, tmp_path: Path):
        target = tmp_path / "src" / "big.py"
        _write(
            target,
            "\n".join(
                [
                    '"""Module docs."""',
                    "",
                    "from __future__ import annotations",
                    "",
                    *[f"VALUE_{i} = {i}" for i in range(900)],
                ]
            ),
        )

        result = debt_scan.fix(
            _ctx(tmp_path, difficulty=1),
            [{"action": "large-file", "file": "src/big.py", "lines": 904, "threshold": 450}],
        )

        assert result.success is True
        content = target.read_text(encoding="utf-8")
        assert content.index("from __future__ import annotations") < content.index("TODO_CLEANUP")
        compile(content, str(target), "exec")

    def test_fix_preserves_use_client_directive(self, tmp_path: Path):
        target = tmp_path / "src" / "Big.tsx"
        _write(
            target,
            "\n".join(
                [
                    '"use client";',
                    "",
                    "import React from 'react';",
                    *[f"export const V{i} = {i};" for i in range(900)],
                ]
            ),
        )

        result = debt_scan.fix(
            _ctx(tmp_path, difficulty=1),
            [{"action": "large-file", "file": "src/Big.tsx", "lines": 903, "threshold": 450}],
        )

        assert result.success is True
        lines = target.read_text(encoding="utf-8").splitlines()
        assert lines[0] == '"use client";'
        assert lines[1].startswith("// TODO_CLEANUP:")


class TestModuleInterface:
    def test_has_name(self):
        assert debt_scan.name == "auto-debt-scan"

    def test_has_scan_callable(self):
        assert callable(debt_scan.scan)

    def test_has_fix_callable(self):
        assert callable(debt_scan.fix)
