"""Plugin scaffold/create/manage tools for mcp-app-factory.

Tools: create-plugin, audit-plugin, export-skill, import-skill,
       scan-importable-plugins, list-templates, get-template-content,
       get-plugin-spec, validate-agent-wizard
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._helpers import (
    logger,
    tool_annotations,
    PLUGIN_ROOT,
    PROJECT_ROOT,
)


# ============================================================================
# Implementation Functions
# ============================================================================


def create_plugin_impl(
    name: str,
    category: str,
    description: str,
    features: Optional[List[str]] = None,
) -> dict:
    """Create a new Augur plugin from templates."""
    logger.info("Creating plugin", extra={"plugin_name": name, "category": category})

    try:
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from scaffold import generate_plugin

        result = generate_plugin(
            name=name,
            category=category,
            description=description,
            features=features,
        )

        logger.info("Plugin created", extra={"plugin": result["plugin_name"]})
        return result

    except Exception as e:
        logger.error("Failed to create plugin", exc_info=True, extra={"plugin_name": name})
        return {"success": False, "error": str(e)}


def export_skill_impl(
    skill_path: str,
    output_dir: Optional[str] = None,
    target: str = "claude-code",
) -> dict:
    """Export a skill as an external package (stripped of Augur extensions)."""
    logger.info("Exporting skill", extra={"skill_path": skill_path, "target": target})

    try:
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from skill_exporter import export_skill, VALID_TARGETS

        if target not in VALID_TARGETS:
            return {"success": False, "error": f"Invalid target: {target}. Valid: {VALID_TARGETS}"}

        path = Path(skill_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / skill_path

        if not path.exists():
            return {"success": False, "error": f"Skill path does not exist: {skill_path}"}

        out = Path(output_dir) if output_dir else None
        if not out:
            return {"success": False, "error": "output_dir is required"}

        export_dir = export_skill(str(path), str(out), target=target)

        # export_skill returns a Path to the exported directory
        exported_files = []
        if isinstance(export_dir, Path) and export_dir.exists():
            exported_files = [str(f.relative_to(export_dir)) for f in sorted(export_dir.rglob("*")) if f.is_file()]

        return {
            "success": True,
            "skill_path": str(path),
            "output_dir": str(export_dir),
            "target": target,
            "files_exported": exported_files,
        }

    except Exception as e:
        logger.error("Failed to export skill", exc_info=True)
        return {"success": False, "error": str(e)}


def import_skill_impl(
    source: str,
    # Track 3b: target_bundle is the plugin BUNDLE id (lifestyle/ai/dev/...),
    # not a hub id from config/system/hubs.yaml.
    target_bundle: str = "lifestyle",
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict:
    """Import an external plugin into Augur.

    Supports importing from:
    - Local directories (plugin folder structure)
    - Zip files (compressed plugins)
    - Hidden folders (.claude-plugins, etc.)
    """
    logger.info("Importing skill", extra={"source": source, "bundle": target_bundle})

    try:
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from skill_importer import import_plugin

        result = import_plugin(
            source=source,
            target_bundle=target_bundle,
            dry_run=dry_run,
            overwrite=overwrite,
        )
        return result

    except Exception as e:
        logger.error("Failed to import skill", exc_info=True)
        return {"success": False, "error": str(e)}


def scan_importable_plugins_impl() -> dict:
    """Scan common locations for importable plugins."""
    logger.info("Scanning for importable plugins")

    try:
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from skill_importer import scan_for_plugins, COMMON_PLUGIN_SOURCES

        plugins = scan_for_plugins()
        return {
            "success": True,
            "count": len(plugins),
            "plugins": plugins,
            "sources_scanned": [s[0] for s in COMMON_PLUGIN_SOURCES],
        }

    except Exception as e:
        logger.error("Failed to scan for plugins", exc_info=True)
        return {"success": False, "error": str(e)}


def audit_plugin_impl(name: Optional[str] = None) -> dict:
    """Audit plugin(s) for compliance."""
    logger.info("Auditing plugin(s)", extra={"plugin_name": name or "all"})

    try:
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from audit import load_spec, discover_plugins, audit_plugin as run_audit, audit_all_plugins

        spec = load_spec()

        if name:
            plugins = discover_plugins()
            # discover_plugins returns 4-tuples: (bundle, name, path, profile)
            found = [(b, n, p, prof) for b, n, p, prof in plugins if n == name]
            if not found:
                return {"success": False, "error": f"Plugin not found: {name}"}
            bundle, plugin_name, plugin_path, profile = found[0]
            audit = run_audit(plugin_path, plugin_name, bundle, spec, profile=profile)
            audits = [audit]
        else:
            audits = audit_all_plugins(spec)

        results = []
        for audit in audits:
            results.append(
                {
                    "plugin_name": audit.plugin_name,
                    "plugin_path": str(getattr(audit, "plugin_path", "")),
                    "bundle": audit.bundle,
                    "score": round(audit.score, 1),
                    "status": audit.status,
                    "passed": audit.passed,
                    "failed": audit.failed,
                    "issues": [
                        {"rule": r.rule, "message": r.message, "file_path": r.file_path}
                        for r in audit.results
                        if not r.passed
                    ][:10],
                }
            )

        total = len(results)
        passing = sum(1 for r in results if r["status"] == "pass")
        warning = sum(1 for r in results if r["status"] == "warn")
        failing = sum(1 for r in results if r["status"] == "fail")

        return {
            "success": True,
            "summary": {"total": total, "passing": passing, "warning": warning, "failing": failing},
            "plugins": results,
        }

    except Exception as e:
        logger.error("Failed to audit plugins", exc_info=True)
        return {"success": False, "error": str(e)}


# ============================================================================
# Tool Registration
# ============================================================================


def register_plugin_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register plugin scaffold/create/manage tools with the MCP server."""

    @mcp.tool(
        name="create-plugin",
        annotations=tool_annotations(
            {
                "title": "Create Plugin",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def create_plugin_tool(
        name: str,
        category: str,
        description: str,
        features: Optional[List[str]] = None,
    ) -> str:
        """Create a new Augur plugin from templates.

        Args:
            name: Plugin name (will be converted to kebab-case)
            category: Plugin category - one of: system, productivity, personal, business
            description: Short description of the plugin
            features: Optional list of features to enable. Options: mcp, dashboard, api, chains, schemas, backlog, tests. Default: all

        Returns:
            str: JSON with generation results including plugin_path, generated files, and next steps
        """
        metrics.track_tool("create_plugin", skill="mcp-app-factory")
        result = create_plugin_impl(name, category, description, features)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="audit-plugin",
        annotations=tool_annotations(
            {
                "title": "Audit Plugin",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def audit_plugin_tool(name: Optional[str] = None) -> str:
        """Audit plugin(s) for compliance with the plugin specification.

        Args:
            name: Plugin name to audit, or None/empty to audit all plugins

        Returns:
            str: JSON with audit results including score, status, and detailed results
        """
        metrics.track_tool("audit_plugin", skill="mcp-app-factory")
        result = audit_plugin_impl(name)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="export-skill",
        annotations=tool_annotations(
            {
                "title": "Export Skill",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def export_skill_tool(
        skill_path: str,
        output_dir: Optional[str] = None,
        target: str = "claude-code",
    ) -> str:
        """Export an Augur skill as an external package, stripping Augur extensions.

        Exports a skill from any bundle (crew, services, apps, orchestrator)
        as an external package. Layer 2 (Augur extensions) are stripped,
        leaving only the standard Layer 1 core files.

        Args:
            skill_path: Path to the skill directory (e.g., project-brain/capabilities/skills/knowledge)
            output_dir: Output directory (defaults to ~/Desktop/augur-exports)
            target: Export target format - one of: claude-code, mcp-server, python-package

        Returns:
            str: JSON with export results including files exported and stripped
        """
        metrics.track_tool("export_skill", skill="mcp-app-factory")
        result = export_skill_impl(skill_path, output_dir, target)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="import-skill",
        annotations=tool_annotations(
            {
                "title": "Import Skill",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def import_skill_tool(
        source: str,
        target_bundle: str = "lifestyle",
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> str:
        """Import an external plugin into Augur.

        Imports plugins from various sources:
        - Local directories (Claude Code plugin, MCP server, Python package)
        - Zip files (compressed plugins)
        - Hidden folders (.claude-plugins, .cursor/plugins, etc.)

        Args:
            source: Path to plugin directory or zip file
            target_bundle: Augur bundle to import into (apps, services, crew, orchestrator)
            overwrite: If True, overwrite existing skill with same name
            dry_run: If True, show what would be imported without executing

        Returns:
            str: JSON with import results including files copied and generated
        """
        metrics.track_tool("import_skill", skill="mcp-app-factory")
        result = import_skill_impl(source, target_bundle, overwrite, dry_run)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="scan-importable-plugins",
        annotations=tool_annotations(
            {
                "title": "Scan Importable Plugins",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def scan_importable_plugins_tool() -> str:
        """Scan common locations for importable plugins.

        Searches these locations:
        - ~/.claude/plugins, ~/.claude-plugins
        - ~/.cursor/plugins, ~/.cursor/agents
        - ~/Desktop/plugins, ~/Downloads (for zips)
        - .claude-plugins, .cursor/plugins (project-local)

        Returns:
            str: JSON with list of found plugins and their types
        """
        metrics.track_tool("scan_importable_plugins", skill="mcp-app-factory")
        result = scan_importable_plugins_impl()
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="list-templates",
        annotations=tool_annotations(
            {
                "title": "List Templates",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_templates_tool() -> str:
        """List available plugin templates.

        Returns:
            str: JSON with template categories and file names
        """
        metrics.track_tool("list_templates", skill="mcp-app-factory")

        templates_dir = PLUGIN_ROOT / "assets" / "templates"
        if not templates_dir.exists():
            return json.dumps({"success": False, "error": "Templates directory not found"})

        templates = []
        for template_file in sorted(templates_dir.glob("*.template")):
            templates.append({"name": template_file.name, "path": str(template_file)})

        readme = templates_dir / "README.md"
        if readme.exists():
            templates.append({"name": "README.md", "path": str(readme)})

        return json.dumps(
            {
                "success": True,
                "templates_dir": str(templates_dir),
                "count": len(templates),
                "templates": templates,
            },
            indent=2,
        )

    @mcp.tool(
        name="get-template-content",
        annotations=tool_annotations(
            {
                "title": "Get Template Content",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_template_content_tool(template_name: str) -> str:
        """Get the content of a specific template.

        Args:
            template_name: Template file name (e.g., "dashboard.yaml.template")

        Returns:
            str: JSON with template content
        """
        metrics.track_tool("get_template_content", skill="mcp-app-factory")

        templates_dir = PLUGIN_ROOT / "assets" / "templates"
        template_path = templates_dir / template_name

        if not template_path.exists():
            return json.dumps({"success": False, "error": f"Template not found: {template_name}"})

        try:
            content = template_path.read_text()
            return json.dumps(
                {
                    "success": True,
                    "name": template_name,
                    "path": str(template_path),
                    "content": content,
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-plugin-spec",
        annotations=tool_annotations(
            {
                "title": "Get Plugin Spec",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_plugin_spec_tool() -> str:
        """Get the plugin specification schema.

        Returns:
            str: JSON with the full plugin specification
        """
        metrics.track_tool("get_plugin_spec", skill="mcp-app-factory")

        spec_path = PLUGIN_ROOT / "plugin-spec.yaml"
        if not spec_path.exists():
            return json.dumps({"success": False, "error": "Plugin spec not found"})

        try:
            import yaml

            with open(spec_path) as f:
                spec = yaml.safe_load(f)
            return json.dumps({"success": True, "path": str(spec_path), "spec": spec}, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="validate-agent-wizard",
        annotations=tool_annotations(
            {
                "title": "Validate Agent Wizard",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def validate_agent_wizard_tool(name: str, layer: str = "vertical") -> str:
        """Validate agent wizard name and check if skill exists.

        Args:
            name: Skill name to validate
            layer: Layer (vertical, horizontal, factory)

        Returns:
            str: JSON with validation result
        """
        metrics.track_tool("validate_agent_wizard", skill="mcp-app-factory")

        try:
            # Validate kebab-case
            kebab_case_pattern = re.compile(r"^[a-z][a-z0-9-]*$")
            if not kebab_case_pattern.match(name):
                return json.dumps(
                    {"valid": False, "error": "Must be kebab-case (lowercase letters, numbers, hyphens only)"},
                    indent=2,
                )

            # Check in plugin bundles
            skill_path = PROJECT_ROOT / "plugins" / layer / "skills" / name
            if skill_path.exists():
                return json.dumps(
                    {
                        "valid": False,
                        "exists": True,
                        "error": f'Skill "{name}" already exists in {layer} layer',
                        "path": str(skill_path),
                    },
                    indent=2,
                )

            return json.dumps({"valid": True, "exists": False, "path": str(skill_path)}, indent=2)

        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            return json.dumps({"valid": False, "error": str(e)})
