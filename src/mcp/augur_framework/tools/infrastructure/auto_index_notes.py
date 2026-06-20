"""Skill-specific MCP tools for the auto-index-notes dashboard surface."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config.paths import get_project_brain_skills_dir, get_project_root
from src.lib.ops_protocol import OpsContext
from src.mcp.augur_shared.annotations import tool_annotations

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

SKILL_ID = "auto-index-notes"
SKILL_OWNER = "ai"

INDEX_TARGETS = [
    "Vault-backed notes directories resolved via get_skill_data_dir(skill) / notes",
    "Markdown files tracked as *.md except private underscore-prefixed files",
    "Per-skill cache file _index.cache.yaml rebuilt when entries are missing",
]

REPAIR_FLOW = [
    {
        "title": "Scan for drift",
        "detail": "Compare markdown files on disk against cache entries already recorded in _index.cache.yaml.",
    },
    {
        "title": "Rebuild the cache",
        "detail": "Use notes_lib.write_index_cache when available, then fall back to a minimal inline cache builder.",
    },
    {
        "title": "Commit the fix",
        "detail": "Stage the rebuilt cache file and create a focused git commit for each repaired skill.",
    },
]

DIFFICULTY_LEVELS = [
    {
        "id": "d0",
        "label": "Detect",
        "detail": "Find notes directories with unindexed markdown files.",
    },
    {
        "id": "d1",
        "label": "Repair",
        "detail": "Rebuild safe cache files automatically for affected skills.",
    },
    {
        "id": "d2",
        "label": "Analyze",
        "detail": "Extend the scan to structural cache issues and deeper validation.",
    },
]


def _load_skill_module(project_root: Path):
    module_path = get_project_brain_skills_dir(project_root) / SKILL_OWNER / "scripts" / "ops" / "index_notes.py"
    spec = importlib.util.spec_from_file_location("auto_index_notes_ops", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def register_auto_index_notes_tools(
    mcp: FastMCP,
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """Register auto-index-notes skill-specific tools."""

    @mcp.tool(
        name="auto-index-notes-status",
        annotations=tool_annotations(
            {
                "title": "Get Auto Index Notes Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_auto_index_notes_status_tool() -> str:
        """Return a live note-index scan summary for the auto-index-notes skill."""
        metrics.track_tool("get_auto_index_notes_status")

        project_root = get_project_root()
        module = _load_skill_module(project_root)
        ctx = OpsContext(project_root=project_root, dry_run=True)
        scan_result = module.scan(ctx)
        discovered = module._discover_notes_dirs(project_root)
        notes_lib_path = module._resolve_notes_lib_path(project_root)

        issues = [
            {
                "skill": issue.get("skill", ""),
                "path": issue.get("path", ""),
                "unindexed_count": int(issue.get("unindexed_count", 0) or 0),
                "unindexed_files": issue.get("unindexed_files", []) or [],
            }
            for issue in scan_result.issues
        ]
        issues.sort(key=lambda issue: (-issue["unindexed_count"], issue["skill"]))

        notes_directories = len(discovered)
        drifted_directories = len(issues)
        unindexed_files = sum(issue["unindexed_count"] for issue in issues)

        payload = {
            "skill": SKILL_ID,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "status": "healthy" if drifted_directories == 0 else "degraded",
            "summary": {
                "notesDirectories": notes_directories,
                "driftedDirectories": drifted_directories,
                "healthyDirectories": max(notes_directories - drifted_directories, 0),
                "unindexedFiles": unindexed_files,
                "notesLibAvailable": notes_lib_path is not None,
                "fallbackMode": notes_lib_path is None,
            },
            "issues": issues,
            "monitoredTargets": INDEX_TARGETS,
            "repairFlow": REPAIR_FLOW,
            "difficultyLevels": DIFFICULTY_LEVELS,
        }
        return json.dumps(payload, indent=2)


__all__ = ["register_auto_index_notes_tools"]
