"""sync_agents/adapters/windsurf.py — Windsurf adapter."""
from __future__ import annotations
import json
from pathlib import Path

from .base import BaseAdapter
from ..constants import (
    PROJECT_ROOT,
    SOURCE_RULES_LABEL,
    MCP_CONFIG_TEMPLATE,
    GENERATED_FILES,
    logger,
)
from ..engine import write_generated_file
from ..templates import locate_mcp_python, render_rules_projection


class WindsurfAdapter(BaseAdapter):
    adapter_name = "windsurf"

    def get_managed_files(self) -> list[str]:
        return [
            ".windsurfrules",
            ".windsurf/rules/",
            ".windsurf/skills/",
            ".windsurf/mcp.json",
        ]

    def get_state_files(self) -> list[str]:
        home = str(Path.home())
        return [
            f"{home}/.windsurf/history/",
            f"{home}/.windsurf/sessions/",
            f"{home}/.windsurf/cache/",
        ]

    def detect_installed(self) -> bool:
        import shutil
        return shutil.which("windsurf") is not None

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        deleted = super().cleanup(exclude_paths=exclude_paths, dry_run=dry_run)
        if dry_run:
            return deleted
        windsurf_root = PROJECT_ROOT / ".windsurf"
        if windsurf_root.exists():
            try:
                windsurf_root.rmdir()
                deleted.append(".windsurf/")
            except OSError:
                pass
        return deleted

    def sync_rules(self, content: str) -> None:
        resolved = render_rules_projection(content)
        write_generated_file(
            PROJECT_ROOT / ".windsurfrules",
            resolved,
            source=SOURCE_RULES_LABEL,
        )
        write_generated_file(
            PROJECT_ROOT / ".windsurf" / "rules" / "augur.md",
            resolved,
            source=SOURCE_RULES_LABEL,
        )

    def generate_mcp_config(self) -> None:
        """Generate resolved MCP config for Windsurf (.windsurf/mcp.json).

        Reads the template from src/config/mcp_config.template.json,
        resolves variables, and writes to .windsurf/mcp.json.
        Merges with existing config to preserve user-added MCP servers.
        """
        if not MCP_CONFIG_TEMPLATE.exists():
            logger.warning(f"MCP config template not found: {MCP_CONFIG_TEMPLATE}")
            return

        try:
            template_content = MCP_CONFIG_TEMPLATE.read_text(encoding="utf-8")

            # Resolve template variables (POSIX paths keep JSON parsing safe on Windows).
            resolved = template_content.replace("${AUGUR_ROOT}", PROJECT_ROOT.as_posix())

            resolved = resolved.replace("${AUGUR_PYTHON}", locate_mcp_python())
            resolved = resolved.replace("${AUGUR_CLIENT_ID}", "windsurf")

            # Parse to ensure valid JSON
            config = json.loads(resolved)

            target = PROJECT_ROOT / ".windsurf" / "mcp.json"
            target.parent.mkdir(parents=True, exist_ok=True)

            # Merge with existing config if present
            if target.exists():
                try:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                    if not isinstance(existing, dict):
                        existing = {}
                    if "mcpServers" not in existing:
                        existing["mcpServers"] = {}
                    existing["mcpServers"]["augur"] = config["mcpServers"]["augur"]
                    config = existing
                except (json.JSONDecodeError, OSError):
                    pass

            target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            GENERATED_FILES.append(target)
            logger.info(f"✅ Generated {target.relative_to(PROJECT_ROOT)} (MCP config)")
        except Exception as e:
            logger.error(f"Failed to generate MCP config for Windsurf: {e}")
