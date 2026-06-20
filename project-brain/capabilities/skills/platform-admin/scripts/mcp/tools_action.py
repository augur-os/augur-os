"""Platform Admin action MCP tools — repo health, nightly checks, dependency graph, backup, CI, releases."""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import asyncio
import json
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._shared import _run_python_script_async, tool_annotations
from src.plugins.context import get_dependency_graph


def register_action_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register platform-admin action tools."""

    @mcp.tool(
        name="check-repo-health",
        annotations=tool_annotations(
            {
                "title": "Check Repository Health",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def check_repo_health_tool() -> str:
        """Check repository health metrics (size, LFS, stale branches)."""
        metrics.track_tool("check_repo_health", skill="platform-admin")
        result = await _run_python_script_async("project-brain/capabilities/skills/platform-admin/scripts/check_repo_health.py", ["--json"])

        if result.get("success") and isinstance(result.get("result"), dict):
            payload = result["result"]
            score = payload.get("data", {}).get("score")
            summary = payload.get("summary", {})
            return json.dumps(
                {
                    "score": score,
                    "summary": f"{summary.get('high', 0)} high, {summary.get('medium', 0)} medium findings",
                    "last_run": payload.get("data", {}).get("audit_date"),
                    "details": payload,
                },
                indent=2,
                default=str,
            )

        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="run-nightly-checks",
        annotations=tool_annotations(
            {
                "title": "Run DevOps Nightly Checks",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def run_nightly_checks_tool() -> str:
        """Run nightly platform-admin checks (lint, test, dependency audit)."""
        metrics.track_tool("run_nightly_checks", skill="platform-admin")
        result = await _run_python_script_async("project-brain/capabilities/skills/platform-admin/scripts/augur_nightly_checks.py")
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-dependency-graph",
        annotations=tool_annotations(
            {
                "title": "Get Skill Dependency Graph",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_dependency_graph_tool() -> str:
        """Return the skill-level dependency graph with node and edge counts."""
        metrics.track_tool("get_dependency_graph", skill="platform-admin")
        graph = await asyncio.to_thread(get_dependency_graph)
        return json.dumps(
            {
                "success": True,
                "nodes": len(graph),
                "edges": sum(len(v) for v in graph.values()),
                "graph": graph,
            },
            indent=2,
            default=str,
        )

    @mcp.tool(
        name="data-backup",
        annotations=tool_annotations(
            {
                "title": "Create Data Snapshot",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def data_backup_tool(label: str = "mcp") -> str:
        """Create a labeled data snapshot for backup and recovery."""
        metrics.track_tool("data_backup", skill="platform-admin")
        result = await _run_python_script_async(
            "project-brain/capabilities/skills/platform-admin/scripts/data_backup.py",
            ["create", "--label", label],
        )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-infrastructure-health",
        annotations=tool_annotations(
            {
                "title": "Get Infrastructure Health",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_infrastructure_health_tool() -> str:
        """Get infrastructure health status (services, disk, processes)."""
        metrics.track_tool("get_infrastructure_health", skill="platform-admin")
        result = await _run_python_script_async(
            "project-brain/capabilities/skills/platform-admin/scripts/health_check.py",
            ["--json"],
        )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-ci-change-matrix",
        annotations=tool_annotations(
            {
                "title": "Get CI Change Matrix",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_ci_change_matrix_tool() -> str:
        """Detect changed files and compute the CI test matrix."""
        metrics.track_tool("get_ci_change_matrix", skill="platform-admin")
        result = await _run_python_script_async(
            "project-brain/capabilities/skills/platform-admin/scripts/ci_change_detector.py",
            ["--all"],
        )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="list-incident-runbooks",
        annotations=tool_annotations(
            {
                "title": "List Incident Runbooks",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_incident_runbooks_tool(incident: str = "") -> str:
        """List incident runbooks, optionally filtered by incident type."""
        metrics.track_tool("list_incident_runbooks", skill="platform-admin")
        args = ["--json"]
        if incident.strip():
            args.extend(["--incident", incident.strip()])
        result = await _run_python_script_async(
            "project-brain/capabilities/skills/platform-admin/scripts/incident_runbooks.py",
            args,
        )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-release-dry-run",
        annotations=tool_annotations(
            {
                "title": "Get Release Dry Run",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_release_dry_run_tool(skill: str = "platform-admin", bump: str = "patch") -> str:
        """Simulate a release for a skill without publishing (dry run)."""
        metrics.track_tool("get_release_dry_run", skill="platform-admin")
        bump_flag = "--patch"
        if bump == "minor":
            bump_flag = "--minor"
        elif bump == "major":
            bump_flag = "--major"

        result = await _run_python_script_async(
            "project-brain/capabilities/skills/platform-admin/scripts/release.py",
            [skill, bump_flag, "--dry-run", "--skip-tests"],
        )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-refactor-report",
        annotations=tool_annotations(
            {
                "title": "Get Capability Migration Audit Report",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_refactor_report_tool() -> str:
        """Read the latest ops-refactor migration report and expiry data."""
        metrics.track_tool("get_refactor_report", skill="platform-admin")
        from ._loaders import _load_refactor_report
        return json.dumps(
            await asyncio.to_thread(_load_refactor_report),
            indent=2,
            default=str,
        )

    @mcp.tool(
        name="augur-refactor",
        annotations=tool_annotations(
            {
                "title": "Run Augur Refactor",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def augur_refactor_tool(old_name: str, new_name: str, apply: bool = False) -> str:
        """Rename a skill across the codebase."""
        metrics.track_tool("augur_refactor", skill="platform-admin")
        args = [old_name, new_name]
        if apply:
            args.append("--apply")
        result = await _run_python_script_async("project-brain/capabilities/skills/platform-admin/scripts/augur_refactor.py", args)
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-long-term-decisions",
        annotations=tool_annotations(
            {
                "title": "Get Long-Term Decisions",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_long_term_decisions_tool() -> str:
        """Return ADR metadata from the vault ADR directory as a JSON list of decisions."""
        metrics.track_tool("get_long_term_decisions", skill="platform-admin")

        def _scan() -> dict[str, Any]:
            try:
                from src.config.paths import get_adr_dir
                from src.lib.adr_utils import scan_adrs

                decisions_dir = get_adr_dir()
                if not decisions_dir.exists():
                    return {"decisions": [], "error": f"decisions dir not found: {decisions_dir}"}
                adrs = scan_adrs(decisions_dir)
                decisions = [
                    {
                        "id": f"ADR-{a['number']}",
                        "title": a["title"],
                        "status": a["status"],
                        "date": a["date"],
                        "source": a["filename"],
                        "relevance": a.get("hub") or "",
                        "hub": a.get("hub"),
                        "tags": a.get("tags", []),
                        "related": a.get("related", []),
                        "deciders": a.get("deciders", []),
                        "superseded_by": a.get("superseded_by"),
                    }
                    for a in adrs
                ]
                return {"decisions": decisions}
            except Exception as exc:  # pragma: no cover - defensive
                return {"decisions": [], "error": str(exc)}

        result = await asyncio.to_thread(_scan)
        return json.dumps(result, indent=2, default=str)
