"""sync_agents/adapters/cursor.py — Cursor adapter."""
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



class CursorAdapter(BaseAdapter):
    adapter_name = "cursor"

    def get_managed_files(self) -> list[str]:
        home = str(Path.home())
        return [
            ".cursorrules",
            ".cursor/rules/",
            ".cursor/agents/",
            ".cursor/mcp.json",
            ".cursor/memory/",
            f"{home}/.cursor/skills-cursor/",
        ]

    def get_state_files(self) -> list[str]:
        home = str(Path.home())
        return [
            f"{home}/.cursor/projects/",
            f"{home}/.cursor/workspaceStorage/",
            f"{home}/.cursor/User/workspaceStorage/",
            f"{home}/.cursor/.backups/",
        ]

    def detect_installed(self) -> bool:
        import shutil
        return shutil.which("cursor") is not None or (Path.home() / ".cursor").is_dir()

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        deleted = super().cleanup(exclude_paths=exclude_paths, dry_run=dry_run)
        if dry_run:
            return deleted
        cursor_root = PROJECT_ROOT / ".cursor"
        if cursor_root.exists():
            try:
                cursor_root.rmdir()
                deleted.append(".cursor/")
            except OSError:
                pass
        return deleted

    def sync_rules(self, content: str) -> None:
        resolved = render_rules_projection(content)
        # 1. Legacy .cursorrules
        write_generated_file(
            PROJECT_ROOT / ".cursorrules",
            resolved,
            source=SOURCE_RULES_LABEL,
        )

        # 2. Modern .cursor/rules/augur.mdc
        mdc_content = f"""---
description: Augur Project Rules & Context
globs:
alwaysApply: true
---
{resolved}
"""
        write_generated_file(
            PROJECT_ROOT / ".cursor" / "rules" / "augur.mdc",
            mdc_content,
            source=SOURCE_RULES_LABEL,
        )

    def generate_mcp_config(self) -> None:
        """Generate resolved MCP config for Cursor (.cursor/mcp.json).

        Reads the template from src/config/mcp_config.template.json,
        resolves variables, and writes to .cursor/mcp.json.
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
            resolved = resolved.replace("${AUGUR_CLIENT_ID}", "cursor")

            # Parse to ensure valid JSON
            config = json.loads(resolved)

            target = PROJECT_ROOT / ".cursor" / "mcp.json"
            target.parent.mkdir(parents=True, exist_ok=True)

            # Merge with existing config if present
            if target.exists():
                try:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                    if not isinstance(existing, dict):
                        existing = {}
                    if "mcpServers" not in existing:
                        existing["mcpServers"] = {}
                    for server_name in list(existing["mcpServers"]):
                        if server_name.startswith("augur"):
                            del existing["mcpServers"][server_name]
                    existing["mcpServers"].update(config.get("mcpServers", {}))
                    config = existing
                except (json.JSONDecodeError, OSError):
                    pass

            target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            GENERATED_FILES.append(target)
            logger.info(f"✅ Generated {target.relative_to(PROJECT_ROOT)} (MCP config)")
        except Exception as e:
            logger.error(f"Failed to generate MCP config for Cursor: {e}")

    def sync_subagents(self) -> None:
        """Generate Cursor subagent profiles from non-Claude master agents (ADR-464).

        Cursor 2.4+ natively reads .claude/agents/, so Claude-mastered agents
        are skipped. Only non-Claude masters need adapted copies.
        Plugin agents are also skipped since Cursor reads them natively.
        """
        from ..agent_parser import scan_agent_dirs, collect_masters, scan_plugin_agents, ADAPTED_COPY_COMMENT
        from ..model_mapping import resolve_model

        agents = scan_agent_dirs(PROJECT_ROOT) + scan_plugin_agents()
        masters = collect_masters(agents)
        if not masters:
            return

        agents_dir = PROJECT_ROOT / ".cursor" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        generated_names: set[str] = set()
        for name, master in sorted(masters.items()):
            # Cursor natively reads .claude/agents/ and Claude plugins — skip both
            if master.master_client in ("claude-code", "cursor") or master.client_dir.startswith("plugin:"):
                continue

            cursor_model = resolve_model(master.master_client, "cursor", master.model)
            description = master.description or f"{name} agent"
            readonly = "true" if master.mode == "plan" else "false"

            body = master.body

            marker = ADAPTED_COPY_COMMENT.format(master_client=master.master_client)
            content = f"---\nmodel: {cursor_model}\ndescription: \"{description}\"\nreadonly: {readonly}\n---\n{marker}\n\n{body}"

            target = agents_dir / f"{name}.md"
            try:
                source_ref = str(master.path.relative_to(PROJECT_ROOT))
            except ValueError:
                source_ref = f"{master.client_dir}/{master.name}.md"
            write_generated_file(target, content, source=source_ref)
            generated_names.add(name)
            logger.info(f"  → Cursor agent: {name} (model={cursor_model})")

        self._cleanup_orphan_agents(agents_dir, generated_names)

    def sync_memory(self) -> None:
        """Sync canonical memory to .cursor/memory/ (ADR-057)."""
        try:
            memory_content = self.get_projected_memory_content()
            if not memory_content:
                return
            target_dir = PROJECT_ROOT / ".cursor" / "memory"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "augur-memory.md"
            target.write_text(memory_content, encoding="utf-8")
            logger.info(f"✅ Synced memory to {target.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            logger.error(f"Failed to sync memory for Cursor: {e}")
