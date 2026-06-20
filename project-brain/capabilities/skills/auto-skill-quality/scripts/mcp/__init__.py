"""MCP tools for auto-skill-quality skill."""
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
import json
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:
    import logging

    def get_entity_logger(name: str):
        return logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations


logger = get_entity_logger("mcp.adaptive.skill-structure")


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register skill structure scanning tools with the MCP server."""
    logger.info("Registering auto-skill-quality MCP tools...")

    @mcp.tool(
        name="scan-skill-structure",
        annotations=tool_annotations({
            "title": "Scan Skill Structure",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def scan_skill_structure_tool() -> str:
        """Scan all skill directories for structure violations — banned files, deprecated patterns, missing metadata."""
        metrics.track_tool("scan_skill_structure", skill="auto-skill-quality")

        from src.config.paths import get_all_client_skill_dirs, get_project_root

        project_root = get_project_root()

        # Import scan function from sibling script
        from ..scan_structure import scan_skills

        all_violations: list[dict] = []
        skills_scanned = 0

        for skills_dir in get_all_client_skill_dirs(project_root):
            if not skills_dir.exists():
                continue
            skill_count = sum(
                1
                for d in skills_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )
            skills_scanned += skill_count
            all_violations.extend(scan_skills(skills_dir))

        errors = [v for v in all_violations if v["severity"] == "error"]
        warnings = [v for v in all_violations if v["severity"] == "warning"]

        payload = {
            "success": True,
            "skills_scanned": skills_scanned,
            "total_violations": len(all_violations),
            "errors": len(errors),
            "warnings": len(warnings),
            "violations": all_violations,
        }
        return json.dumps(payload, indent=2)

    @mcp.tool(
        name="skill-resolvable-report",
        annotations=tool_annotations({
            "title": "Skill Resolvability Report",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def skill_resolvable_report_tool() -> str:
        """Return the latest skill-coverage audit (ADR-741).

        Detects unrouted intents, routing collisions, orphaned skills, and stale
        capability entries across the Augur skill catalog. Re-runs the audit when
        the cached JSON is older than one hour so the dashboard card always sees
        a fresh report without a full loop run.
        """
        import time

        metrics.track_tool("skill_resolvable_report", skill="auto-skill-quality")

        from src.config.paths import get_runtime_dir

        from ..check_resolvable import run_audit

        report_path = get_runtime_dir() / "quality" / "resolvable-report.json"
        cache_max_age_seconds = 60 * 60  # 1 hour

        report: dict | None = None
        if report_path.is_file():
            try:
                age = time.time() - report_path.stat().st_mtime
            except OSError:
                age = float("inf")
            if age <= cache_max_age_seconds:
                try:
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    report = None

        if report is None:
            report = run_audit()

        return json.dumps(report, indent=2)

    logger.info("auto-skill-quality MCP tools registered")


__all__ = ["register_tools"]
