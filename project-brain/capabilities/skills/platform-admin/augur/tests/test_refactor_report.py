"""
Tests for the get-refactor-report MCP tool (ADR-253).

Validates YAML report loading, expiry computation, and error handling.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Stub out heavy MCP dependencies so we can import the module under test
# without requiring the full augur runtime.
# ---------------------------------------------------------------------------

_stubs = {
    "src.mcp.augur_shared.annotations": types.ModuleType("src.mcp.augur_shared.annotations"),
    "src.mcp.augur_shared.config": types.ModuleType("src.mcp.augur_shared.config"),
    "src.mcp.augur_shared.logging": types.ModuleType("src.mcp.augur_shared.logging"),
    "src": types.ModuleType("src"),
    "src.config": types.ModuleType("src.config"),
    "src.config.paths": types.ModuleType("src.config.paths"),
    "src.lib": types.ModuleType("src.lib"),
    "src.lib.skill_paths": types.ModuleType("src.lib.skill_paths"),
    "src.plugins": types.ModuleType("src.plugins"),
    "src.plugins.context": types.ModuleType("src.plugins.context"),
}

_stubs["src.mcp.augur_shared.annotations"].tool_annotations = lambda x: x  # type: ignore[attr-defined]
_stubs["src.mcp.augur_shared.config"].get_project_root = MagicMock(return_value=Path("/fake"))  # type: ignore[attr-defined]
_stubs["src.mcp.augur_shared.config"].get_skill_data_dir = MagicMock(return_value=Path("/fake"))  # type: ignore[attr-defined]
_stubs["src.mcp.augur_shared.logging"].get_entity_logger = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]
_stubs["src.config.paths"].get_python_executable = MagicMock(return_value="python3")  # type: ignore[attr-defined]
_stubs["src.lib.skill_paths"].get_own_data_dir = MagicMock(return_value=Path("/fake"))  # type: ignore[attr-defined]
_stubs["src.plugins.context"].get_dependency_graph = MagicMock(return_value={})  # type: ignore[attr-defined]

for name, mod in _stubs.items():
    sys.modules.setdefault(name, mod)

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MCP_DIR = Path(__file__).resolve().parents[2] / "scripts" / "mcp"
_mcp_pkg_name = "platform_admin_test_mcp"
if _mcp_pkg_name not in sys.modules:
    _pkg_spec = importlib.util.spec_from_file_location(
        _mcp_pkg_name,
        MCP_DIR / "__init__.py",
        submodule_search_locations=[str(MCP_DIR)],
    )
    assert _pkg_spec is not None and _pkg_spec.loader is not None
    _pkg_module = importlib.util.module_from_spec(_pkg_spec)
    sys.modules[_mcp_pkg_name] = _pkg_module
    _pkg_spec.loader.exec_module(_pkg_module)

_loaders = importlib.import_module(f"{_mcp_pkg_name}._loaders")
_load_refactor_report = _loaders._load_refactor_report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def reports_dir(tmp_path: Path) -> Path:
    """Create a temporary reports directory with sample data."""
    d = tmp_path / "reports"
    d.mkdir(parents=True)
    return d


@pytest.fixture()
def sample_report() -> dict:
    """Minimal report matching the schema the dashboard expects."""
    return {
        "generated": "2026-03-07T12:00:00Z",
        "client": "claude-code",
        "summary": {
            "total_patterns": 3,
            "migrate": 1,
            "enhance": 1,
            "explore": 1,
            "skip": 0,
            "est_token_savings": "5K/session",
            "est_latency_savings": "10s/invocation",
        },
        "findings": [
            {
                "id": "test-finding",
                "title": "Test finding",
                "classification": "MIGRATE",
                "impact": "HIGH",
                "effort": "S",
                "priority": "P0",
                "current_pattern": "old way",
                "new_capability": "new way",
                "migration_path": "1. do thing\n2. verify",
                "files_to_change": ["src/foo.py"],
                "risk": "none",
            }
        ],
        "parity": {
            "agents": [],
            "top_implementations": [],
        },
        "next_steps": [
            {"timeframe": "immediate", "action": "Do the thing"},
        ],
    }


def _write_report(reports_dir: Path, name: str, data: dict) -> Path:
    p = reports_dir / name
    p.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return p


def _write_expiry(reports_dir: Path, last_run: str, expires_at: str) -> Path:
    p = reports_dir / "ops-refactor-expiry.yaml"
    p.write_text(
        yaml.dump(
            {"expiry_days": 14, "last_run": last_run, "expires_at": expires_at},
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    return p


def _load_with_root(root: Path) -> dict:
    """Call _load_refactor_report with a patched platform-admin data dir."""
    with patch(
        f"{_mcp_pkg_name}._loaders.get_own_data_dir",
        return_value=root,
    ):
        return _load_refactor_report()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoadRefactorReport:
    """Tests for _load_refactor_report."""

    def test_returns_report_and_expiry(
        self, tmp_path: Path, reports_dir: Path, sample_report: dict
    ) -> None:
        _write_report(reports_dir, "ops-refactor-2026-03-07.yaml", sample_report)
        future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        past = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
        _write_expiry(reports_dir, past, future)

        result = _load_with_root(tmp_path)

        assert result["report"] is not None
        assert result["report"]["client"] == "claude-code"
        assert result["report"]["summary"]["migrate"] == 1
        assert result["expiry"] is not None
        assert result["expiry"]["is_expired"] is False
        assert result["expiry"]["days_until_expiry"] >= 9

    def test_picks_latest_report(
        self, tmp_path: Path, reports_dir: Path, sample_report: dict
    ) -> None:
        old = {**sample_report, "generated": "2026-03-06T12:00:00Z", "client": "old"}
        new = {**sample_report, "generated": "2026-03-07T12:00:00Z", "client": "new"}
        _write_report(reports_dir, "ops-refactor-2026-03-06.yaml", old)
        _write_report(reports_dir, "ops-refactor-2026-03-07.yaml", new)

        result = _load_with_root(tmp_path)

        assert result["report"]["client"] == "new"

    def test_expired_report(
        self, tmp_path: Path, reports_dir: Path, sample_report: dict
    ) -> None:
        _write_report(reports_dir, "ops-refactor-2026-03-01.yaml", sample_report)
        past = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        expired = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
        _write_expiry(reports_dir, past, expired)

        result = _load_with_root(tmp_path)

        assert result["expiry"]["is_expired"] is True
        assert result["expiry"]["days_until_expiry"] < 0

    def test_no_report_files(self, tmp_path: Path, reports_dir: Path) -> None:
        result = _load_with_root(tmp_path)

        assert result["report"] is None
        assert result["expiry"] is None

    def test_no_reports_directory(self, tmp_path: Path) -> None:
        result = _load_with_root(tmp_path)

        assert result["report"] is None
        assert result["expiry"] is None

    def test_malformed_expiry(
        self, tmp_path: Path, reports_dir: Path, sample_report: dict
    ) -> None:
        _write_report(reports_dir, "ops-refactor-2026-03-07.yaml", sample_report)
        expiry_file = reports_dir / "ops-refactor-expiry.yaml"
        expiry_file.write_text(
            "expires_at: not-a-date\nlast_run: also-bad\n", encoding="utf-8"
        )

        result = _load_with_root(tmp_path)

        assert result["report"] is not None
        assert result["expiry"] is not None
        assert result["expiry"]["is_expired"] is True
        assert result["expiry"]["days_until_expiry"] == 0

    def test_report_has_expected_fields(
        self, tmp_path: Path, reports_dir: Path, sample_report: dict
    ) -> None:
        _write_report(reports_dir, "ops-refactor-2026-03-07.yaml", sample_report)

        result = _load_with_root(tmp_path)
        report = result["report"]

        assert "generated" in report
        assert "client" in report
        assert "summary" in report
        assert "findings" in report
        assert "parity" in report
        assert "next_steps" in report

    def test_findings_structure(
        self, tmp_path: Path, reports_dir: Path, sample_report: dict
    ) -> None:
        _write_report(reports_dir, "ops-refactor-2026-03-07.yaml", sample_report)

        result = _load_with_root(tmp_path)
        finding = result["report"]["findings"][0]

        assert finding["id"] == "test-finding"
        assert finding["classification"] == "MIGRATE"
        assert finding["impact"] == "HIGH"
        assert finding["effort"] == "S"
        assert finding["priority"] == "P0"
        assert isinstance(finding["files_to_change"], list)

    def test_expiry_fields(
        self, tmp_path: Path, reports_dir: Path, sample_report: dict
    ) -> None:
        _write_report(reports_dir, "ops-refactor-2026-03-07.yaml", sample_report)
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        past = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        _write_expiry(reports_dir, past, future)

        result = _load_with_root(tmp_path)
        expiry = result["expiry"]

        assert "expires_at" in expiry
        assert "last_run" in expiry
        assert "is_expired" in expiry
        assert "days_until_expiry" in expiry
        assert isinstance(expiry["is_expired"], bool)
        assert isinstance(expiry["days_until_expiry"], int)

    def test_ignores_non_report_yaml_files(
        self, tmp_path: Path, reports_dir: Path
    ) -> None:
        """Expiry file should not be treated as a report."""
        _write_expiry(
            reports_dir,
            (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            (datetime.now(timezone.utc) + timedelta(days=13)).isoformat(),
        )
        # Also put a non-matching yaml file
        (reports_dir / "some-other-file.yaml").write_text("key: value\n")

        result = _load_with_root(tmp_path)

        assert result["report"] is None
        assert result["expiry"] is not None
