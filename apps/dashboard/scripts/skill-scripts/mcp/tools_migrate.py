"""Migration/upgrade tools for mcp-app-factory.

Tools: migrate-analyze, migrate-generate-files, migrate-transform,
       list-migration-candidates
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._helpers import (
    logger,
    tool_annotations,
    PLUGIN_ROOT,
)


# ============================================================================
# Implementation Functions
# ============================================================================


def migrate_analyze_impl(skill_name: str) -> dict:
    """Analyze migration readiness for a skill by name."""
    logger.info("Analyzing skill migration", extra={"skill_name": skill_name})

    try:
        if not skill_name:
            return {"success": False, "error": "skill_name is required"}

        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from migrate import analyze_skill, find_skill

        skill_info = find_skill(skill_name)
        if not skill_info:
            return {"success": False, "error": f"Skill not found: {skill_name}"}

        bundle, _, skill_path = skill_info
        analysis = analyze_skill(skill_path, skill_name, bundle)

        return {
            "success": True,
            "skill_name": skill_name,
            "skill_path": str(skill_path),
            "migration_score": round(analysis.migration_score, 1),
            "summary": {
                "missing_required": len(analysis.missing_required),
                "missing_optional": len(analysis.missing_optional),
                "print_statements": len(analysis.uses_print),
                "logging_imports": len(analysis.uses_direct_logging),
                "hardcoded_paths": len(analysis.hardcoded_paths),
                "dashboard_issues": len(analysis.dashboard_yaml_issues),
            },
            "details": {
                "missing_required": analysis.missing_required[:10],
                "missing_optional": analysis.missing_optional[:10],
                "print_statements": [
                    {"file": str(p["file"]), "line": p["line"], "content": p["content"][:100]}
                    for p in analysis.uses_print[:10]
                ],
                "logging_imports": [
                    {"file": str(p["file"]), "line": p["line"]}
                    for p in analysis.uses_direct_logging[:10]
                ],
                "hardcoded_paths": [
                    {
                        "file": str(p["file"]),
                        "line": p["line"],
                        "path": str(p.get("path") or p.get("content") or "")[:80],
                    }
                    for p in analysis.hardcoded_paths[:10]
                ],
                "dashboard_issues": analysis.dashboard_yaml_issues[:10],
            },
        }

    except Exception as e:
        logger.error("Failed to analyze skill migration", exc_info=True)
        return {"success": False, "error": str(e)}


def migrate_generate_files_impl(
    skill_name: str,
    generate_files: bool = True,
    force: bool = False,
) -> dict:
    """Generate missing migration files for a skill."""
    logger.info("Generating migration files", extra={"skill_name": skill_name, "force": force})

    try:
        if not skill_name:
            return {"success": False, "error": "skill_name is required"}

        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from migrate import analyze_skill, find_skill, generate_missing_files

        skill_info = find_skill(skill_name)
        if not skill_info:
            return {"success": False, "error": f"Skill not found: {skill_name}"}

        bundle, _, skill_path = skill_info
        analysis = analyze_skill(skill_path, skill_name, bundle)

        created: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []

        if generate_files:
            gen_result = generate_missing_files(analysis, force=force, dry_run=False)
            created = gen_result.get("created", [])
            skipped = gen_result.get("skipped", [])
            errors = gen_result.get("errors", [])

        return {
            "success": len(errors) == 0,
            "skill_name": skill_name,
            "skill_path": str(skill_path),
            "files_created": created,
            "files_skipped": skipped,
            "errors": errors,
            "next_steps": [
                "Run transform to fix logging and paths",
                "Run audit to verify compliance",
                "Review generated files and customize as needed",
            ],
        }

    except Exception as e:
        logger.error("Failed to generate migration files", exc_info=True)
        return {"success": False, "error": str(e)}


def migrate_transform_impl(
    skill_name: str,
    fix_print: bool = True,
    fix_logging: bool = True,
    fix_paths: bool = True,
) -> dict:
    """Apply migration code transforms to a skill."""
    logger.info(
        "Applying migration transforms",
        extra={
            "skill_name": skill_name,
            "fix_print": fix_print,
            "fix_logging": fix_logging,
            "fix_paths": fix_paths,
        },
    )

    try:
        if not skill_name:
            return {"success": False, "error": "skill_name is required"}

        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from migrate import find_skill
        from transform import apply_transforms

        skill_info = find_skill(skill_name)
        if not skill_info:
            return {"success": False, "error": f"Skill not found: {skill_name}"}

        _, _, skill_path = skill_info
        result = apply_transforms(
            skill_path=skill_path,
            skill_name=skill_name,
            fix_logging=fix_logging,
            fix_paths=fix_paths,
            fix_print=fix_print,
            dry_run=False,
        )

        print_transforms = 0
        logging_transforms = 0
        path_transforms = 0
        for change in result.transformations:
            if not change.applied:
                continue
            if change.transform_type == "print_to_logger":
                print_transforms += 1
            elif change.transform_type == "logging_import":
                logging_transforms += 1
            elif change.transform_type == "hardcoded_path":
                path_transforms += 1

        return {
            "success": len(result.errors) == 0,
            "skill_name": skill_name,
            "total_changes": result.total_changes,
            "print_transforms": print_transforms,
            "logging_transforms": logging_transforms,
            "path_transforms": path_transforms,
            "files_modified": sorted(set(result.files_modified)),
            "errors": result.errors,
        }

    except Exception as e:
        logger.error("Failed to apply migration transforms", exc_info=True)
        return {"success": False, "error": str(e)}


# ============================================================================
# Tool Registration
# ============================================================================


def register_migrate_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register migration/upgrade tools with the MCP server."""

    @mcp.tool(
        name="migrate-analyze",
        annotations=tool_annotations(
            {
                "title": "Analyze Migration",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def migrate_analyze_tool(skill_name: str) -> str:
        """Analyze migration readiness for a skill."""
        metrics.track_tool("migrate_analyze", skill="mcp-app-factory")
        result = migrate_analyze_impl(skill_name)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="migrate-generate-files",
        annotations=tool_annotations(
            {
                "title": "Generate Migration Files",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def migrate_generate_files_tool(
        skill_name: str,
        generate_files: bool = True,
        force: bool = False,
    ) -> str:
        """Generate missing migration files for a skill."""
        metrics.track_tool("migrate_generate_files", skill="mcp-app-factory")
        result = migrate_generate_files_impl(skill_name, generate_files, force)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="migrate-transform",
        annotations=tool_annotations(
            {
                "title": "Apply Migration Transforms",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def migrate_transform_tool(
        skill_name: str,
        fix_print: bool = True,
        fix_logging: bool = True,
        fix_paths: bool = True,
    ) -> str:
        """Apply migration transforms to a skill codebase."""
        metrics.track_tool("migrate_transform", skill="mcp-app-factory")
        result = migrate_transform_impl(skill_name, fix_print, fix_logging, fix_paths)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="list-migration-candidates",
        annotations=tool_annotations(
            {
                "title": "List Migration Candidates",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_migration_candidates_tool() -> str:
        """List skills that have migration issues or incomplete augur structure.

        Scans all discovered plugins and checks for common migration indicators:
        - Missing augur/augur.yaml
        - Missing scripts/mcp/__init__.py
        - Missing SKILL.md

        Returns a lightweight list so the block renders without running the
        full per-skill analysis (which requires skill_name argument).

        Returns:
            str: JSON array of {skill, bundle, status, issues}
        """
        metrics.track_tool("list_migration_candidates", skill="mcp-app-factory")

        try:
            sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
            from migrate import discover_skills

            candidates: list[dict] = []

            for bundle, skill_name, skill_path in sorted(discover_skills(), key=lambda t: t[1]):
                issues: list[str] = []

                if not (skill_path / "augur" / "augur.yaml").exists():
                    issues.append("missing augur.yaml")
                if not (skill_path / "scripts" / "mcp" / "__init__.py").exists():
                    issues.append("missing mcp/__init__.py")
                if not (skill_path / "SKILL.md").exists():
                    issues.append("missing SKILL.md")

                if not issues:
                    continue  # Already migrated — skip from candidates list

                candidates.append({
                    "skill": skill_name,
                    "bundle": bundle,
                    "status": "needs-migration",
                    "issues": issues,
                })

            return json.dumps({"candidates": candidates, "total": len(candidates)}, indent=2)

        except Exception as e:
            logger.error(f"list-migration-candidates failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})
