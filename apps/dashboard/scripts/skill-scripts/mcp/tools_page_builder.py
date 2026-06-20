"""
Page Builder MCP tools.

Provides tools for listing and deleting pages created by the
visual page builder. Reads from the vault at
get_vault_dir()/page-builder/templates/.

This module is loaded dynamically by the Augur MCP server
via the plugin tool loading system.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.logging import get_entity_logger
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.config import get_project_root
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

    def get_project_root() -> Path:
        data_dir = os.environ.get("AUGUR_ROOT")
        if data_dir:
            path = Path(data_dir)
            if not path.exists():
                raise FileNotFoundError(f"AUGUR_ROOT path does not exist: {path}")
            return path
        try:
            from src.config.paths import get_project_root as _get_root
            return _get_root()
        except ImportError:
            pass
        inferred = Path(__file__).resolve().parent.parent.parent.parent.parent.parent  # fallback
        if (inferred / "plugins").exists():
            return inferred
        raise FileNotFoundError("Project root not found. Set AUGUR_ROOT environment variable.")


logger = get_entity_logger("mcp.page_builder")


def _get_vault_page_builder_dir() -> Path:
    """Resolve the vault page-builder directory: get_vault_dir()/page-builder/."""
    try:
        from src.config.paths import get_vault_dir
        # Flat vault: get_vault_dir()/{skill}/
        return get_vault_dir() / "page-builder"
    except ImportError:
        import os

        from src.config.path_primitives import resolve_vault_standalone
        return resolve_vault_standalone() / "page-builder"


def _get_templates_dir() -> Path:
    """Resolve the vault templates directory."""
    return _get_vault_page_builder_dir() / "templates"


def _get_skill_templates_file() -> Path:
    """Resolve the repo-seeded page-builder templates fallback.

    The historical page-builder skill stored these templates under a legacy
    skill-local data directory.
    After dashboard-script consolidation, the built-in starter templates
    ship with the dashboard scripts as static assets instead.
    """
    return Path(__file__).resolve().parents[1] / "assets" / "page-builder" / "templates.yaml"


def _load_frontmatter_collection(directory: Path) -> list[dict[str, Any]]:
    """Load all .md frontmatter files from a directory."""
    try:
        from src.lib.frontmatter_utils import load_collection
        return load_collection(directory)
    except ImportError:
        import yaml as _yaml
        items: list[dict[str, Any]] = []
        if not directory.is_dir():
            return items
        for md_file in sorted(directory.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue
            end = content.find("\n---", 4)
            if end == -1:
                continue
            try:
                meta = _yaml.safe_load(content[4:end])
            except Exception:
                continue
            if isinstance(meta, dict):
                meta["_source"] = md_file.stem
                items.append(meta)
        return items


def _load_yaml_templates(yaml_path: Path) -> list[dict[str, Any]]:
    """Load templates from a YAML file (templates.yaml format)."""
    if not yaml_path.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("templates", [])
    except Exception:
        pass
    return []


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register page-builder MCP tools with the server."""
    logger.info("Registering page-builder MCP tools...")

    @mcp.tool(
        name="page-builder-list",
        annotations=tool_annotations(
            {
                "title": "List Page Builder Pages",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def page_builder_list_tool() -> str:
        """List all pages created by the page builder.

        Loads pages from both the vault templates directory
        (get_vault_dir()/page-builder/templates/) and the
        skill-local templates.yaml file.

        Returns:
            str: JSON with pages array
        """
        metrics.track_tool("page_builder_list", skill="page-builder")
        try:
            pages: list[dict[str, Any]] = []
            seen_ids: set[str] = set()

            # Load from vault (frontmatter markdown files) — vault takes precedence
            vault_dir = _get_templates_dir()
            if vault_dir.is_dir():
                vault_pages = _load_frontmatter_collection(vault_dir)
                for page in vault_pages:
                    page_id = page.get("id", page.get("_source", ""))
                    page.pop("_source", None)
                    if page_id:
                        seen_ids.add(page_id)
                    page["source"] = "vault"
                    pages.append(page)

            # Load from skill-local templates.yaml (fill in missing ones)
            yaml_path = _get_skill_templates_file()
            yaml_templates = _load_yaml_templates(yaml_path)
            for tmpl in yaml_templates:
                tmpl_id = tmpl.get("id", "")
                if tmpl_id and tmpl_id not in seen_ids:
                    tmpl["source"] = "skill"
                    pages.append(tmpl)
                    seen_ids.add(tmpl_id)

            return json.dumps({"pages": pages}, indent=2, default=str)

        except Exception as e:
            logger.error(f"page-builder-list failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="page-builder-delete",
        annotations=tool_annotations(
            {
                "title": "Delete Page Builder Page",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def page_builder_delete_tool(
        slug: str,
        target_skill: str = "",
        targetSkill: str = "",
    ) -> str:
        """Delete a page generated by the page builder.

        Removes the page template from the vault and optionally
        removes the mounted dashboard files for the target skill.

        Args:
            slug: Page slug/ID to delete
            target_skill: Optional target skill whose mounted page files to clean

        Returns:
            str: JSON with success status and needsRemount flag
        """
        # camelCase alias (ADR-465)
        target_skill = target_skill or targetSkill

        metrics.track_tool("page_builder_delete", skill="page-builder")
        try:
            if not slug:
                return json.dumps({"error": "slug is required"})

            deleted_vault = False
            deleted_yaml = False

            # Delete from vault templates directory
            vault_dir = _get_templates_dir()
            vault_file = vault_dir / f"{slug}.md"
            if vault_file.exists():
                vault_file.unlink()
                deleted_vault = True

            # Remove from skill-local templates.yaml
            yaml_path = _get_skill_templates_file()
            if yaml_path.exists():
                try:
                    import yaml
                    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and "templates" in data:
                        original_len = len(data["templates"])
                        data["templates"] = [
                            t for t in data["templates"]
                            if t.get("id") != slug
                        ]
                        if len(data["templates"]) < original_len:
                            yaml_path.write_text(
                                yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
                                encoding="utf-8",
                            )
                            deleted_yaml = True
                except Exception as yaml_err:
                    logger.warning(f"Could not update templates.yaml: {yaml_err}")

            if not deleted_vault and not deleted_yaml:
                return json.dumps({
                    "error": f"Page not found: {slug}",
                })

            # Clean up mounted dashboard files if target_skill specified
            needs_remount = False
            if target_skill:
                try:
                    project_root = get_project_root()
                    mounted_page = (
                        project_root / "apps" / "dashboard" / "app"
                        / "admin" / "page-builder" / slug
                    )
                    if mounted_page.is_dir():
                        shutil.rmtree(mounted_page)
                        needs_remount = True
                except Exception as mount_err:
                    logger.warning(f"Could not clean mounted page: {mount_err}")

            return json.dumps({
                "success": True,
                "needsRemount": needs_remount,
                "deleted_vault": deleted_vault,
                "deleted_yaml": deleted_yaml,
            }, indent=2, default=str)

        except Exception as e:
            logger.error(f"page-builder-delete failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    logger.info("Page-builder MCP tools registered (2 tools)")


__all__ = ["register_tools"]
