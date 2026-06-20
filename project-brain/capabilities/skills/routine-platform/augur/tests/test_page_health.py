"""Tests for auto-page-health YAML data-source diagnostics."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from src.lib.ops_protocol import OpsContext


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

mod = importlib.import_module("page_health")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(root: Path) -> OpsContext:
    return OpsContext(project_root=root, difficulty=0)


def test_page_health_importable() -> None:
    assert mod is not None


def test_scan_flags_mutation_tool_used_as_passive_yaml_source(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "career" / "augur" / "pages" / "pipeline.yaml",
        """
hub: career
route: pipeline
blocks:
  - type: data-table
    title: Jobs
    mcp_tool: update-career-job
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "src" / "mcp" / "augur_framework" / "domain" / "career.py",
        '@mcp.tool(name="update-career-job")\nasync def update():\n    pass\n',
    )

    result = mod.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert any(issue["action"] == "yaml-passive-mutation-tool" for issue in result.issues)


def test_scan_flags_search_tool_used_as_passive_yaml_source(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "knowledge" / "augur" / "pages" / "search.yaml",
        """
hub: workspace
route: search
blocks:
  - type: data-list
    title: Search
    mcp_tool: search-knowledge
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "src" / "mcp" / "augur_framework" / "domain" / "knowledge.py",
        '@mcp.tool(name="search-knowledge")\nasync def search():\n    pass\n',
    )

    result = mod.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert any(issue["action"] == "yaml-passive-argument-required-tool" for issue in result.issues)


def test_scan_flags_metadata_only_tool_used_as_passive_yaml_source(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "career" / "augur" / "pages" / "pipeline.yaml",
        """
hub: career
route: pipeline
blocks:
  - type: data-table
    title: Jobs
    mcp_tool: list-career-jobs
""".strip()
        + "\n",
    )

    monkeypatch.setattr(mod, "_get_all_tool_names", lambda: set())
    monkeypatch.setattr(
        mod,
        "_probe_tool",
        lambda tool_name, api_url=None: {
            "exists": True,
            "has_data": False,
            "metadata_only": True,
            "error": "metadata-only response",
            "status": 200,
        },
    )

    result = mod.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert any(issue["action"] == "yaml-passive-metadata-only-tool" for issue in result.issues)


def test_scan_reports_mixed_passive_yaml_and_broken_tsx_issues(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "career" / "augur" / "pages" / "pipeline.yaml",
        """
hub: career
route: pipeline
blocks:
  - type: data-table
    title: Jobs
    mcp_tool: update-career-job
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "dashboard" / "pages" / "brain" / "reports" / "page.tsx",
        """
import { useMcpQuery } from "@/features/mcp";

export default function Page() {
  useMcpQuery([], "missing-tsx-tool");
  return null;
}
""".strip()
        + "\n",
    )

    monkeypatch.setattr(mod, "_get_all_tool_names", lambda: set())
    monkeypatch.setattr(
        mod,
        "_probe_tool",
        lambda tool_name, api_url=None: {
            "exists": False,
            "has_data": False,
            "metadata_only": False,
            "error": "HTTP 404",
        },
    )

    result = mod.scan(_ctx(tmp_path))

    actions = {issue["action"] for issue in result.issues}
    assert result.severity == "error"
    assert "yaml-passive-mutation-tool" in actions
    assert "broken-tool" in actions


def test_scan_flags_metadata_only_tool_when_registry_is_available(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "career" / "augur" / "pages" / "pipeline.yaml",
        """
hub: career
route: pipeline
blocks:
  - type: data-table
    title: Jobs
    mcp_tool: list-career-jobs
""".strip()
        + "\n",
    )

    monkeypatch.setattr(mod, "_get_all_tool_names", lambda: {"list-career-jobs"})
    monkeypatch.setattr(
        mod,
        "_probe_tool",
        lambda tool_name, api_url=None: {
            "exists": True,
            "has_data": False,
            "metadata_only": True,
            "error": "metadata-only response",
            "status": 200,
        },
    )

    result = mod.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert any(issue["action"] == "yaml-passive-metadata-only-tool" for issue in result.issues)


def test_scan_flags_unverified_passive_yaml_probe_when_registry_is_available(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "career" / "augur" / "pages" / "pipeline.yaml",
        """
hub: career
route: pipeline
blocks:
  - type: data-table
    title: Jobs
    mcp_tool: list-career-jobs
""".strip()
        + "\n",
    )

    monkeypatch.setattr(mod, "_get_all_tool_names", lambda: {"list-career-jobs"})
    monkeypatch.setattr(
        mod,
        "_probe_tool",
        lambda tool_name, api_url=None: {
            "exists": False,
            "has_data": False,
            "metadata_only": False,
            "error": "connection refused",
        },
    )

    result = mod.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert any(issue["action"] == "yaml-passive-unverified-tool-response" for issue in result.issues)


def test_scan_probes_worktree_dashboard_port(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / ".augur-worktree.yaml",
        "worktree: true\ndashboard_port: 3003\nmcp_port: 8083\n",
    )
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "career" / "augur" / "pages" / "pipeline.yaml",
        """
hub: career
route: pipeline
blocks:
  - type: data-table
    title: Jobs
    mcp_tool: list-career-jobs
""".strip()
        + "\n",
    )

    probed_urls: list[str | None] = []

    def fake_probe(tool_name: str, api_url: str | None = None) -> dict:
        probed_urls.append(api_url)
        return {"exists": True, "has_data": True, "metadata_only": False, "status": 200}

    monkeypatch.setattr(mod, "_get_all_tool_names", lambda: {"list-career-jobs"})
    monkeypatch.setattr(mod, "_probe_tool", fake_probe)

    result = mod.scan(_ctx(tmp_path))

    assert result.severity == "info"
    assert probed_urls == ["http://localhost:3003/api/mcp/tool"]


def test_metadata_only_response_detection() -> None:
    assert mod._is_metadata_only_response({"skill": "demo", "status": "ok", "version": "1.0.0"}) is True
    assert mod._is_metadata_only_response({"success": True, "data": [{"name": "real"}]}) is False
