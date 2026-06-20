"""sync_agents/adapters/kimi.py — Kimi CLI adapter."""
from __future__ import annotations
import json
import os
from pathlib import Path

from .base import BaseAdapter
from ..constants import (
    PROJECT_ROOT,
    MCP_CONFIG_TEMPLATE,
    SOURCE_RULES_LABEL,
    logger,
)
from ..engine import write_generated_file
from ..templates import locate_mcp_python, render_rules_projection


class KimiAdapter(BaseAdapter):
    """Kimi CLI adapter.

    Kimi stores MCP config in ~/.kimi/mcp.json and reads project
    instructions from AGENTS.md in the working directory via the
    ${KIMI_AGENTS_MD} system prompt variable.
    """

    adapter_name = "kimi"

    def get_managed_files(self) -> list[str]:
        home = str(Path.home())
        return [
            "AGENTS.md",
            f"{home}/.kimi/mcp.json",
            f"{home}/.kimi/augur-memory.md",
        ]

    def get_state_files(self) -> list[str]:
        home = str(Path.home())
        return [
            f"{home}/.kimi/history/",
            f"{home}/.kimi/sessions/",
            f"{home}/.kimi/cache/",
        ]

    def detect_installed(self) -> bool:
        import shutil
        return shutil.which("kimi") is not None

    def sync_rules(self, content: str) -> None:
        """Write AGENTS.md to project root (Kimi auto-loads via ${KIMI_AGENTS_MD})."""
        resolved = render_rules_projection(content)
        write_generated_file(
            PROJECT_ROOT / "AGENTS.md",
            resolved,
            source=SOURCE_RULES_LABEL,
        )

    def generate_mcp_config(self) -> None:
        """Generate MCP config for Kimi CLI at ~/.kimi/mcp.json.

        Uses the same template as other adapters but writes to the
        user's home directory since Kimi is a global CLI tool.
        """
        if not MCP_CONFIG_TEMPLATE.exists():
            logger.warning(f"MCP config template not found: {MCP_CONFIG_TEMPLATE}")
            return

        try:
            template_content = MCP_CONFIG_TEMPLATE.read_text(encoding="utf-8")

            # POSIX paths keep JSON parsing safe on Windows.
            config_text = template_content
            config_text = config_text.replace("${AUGUR_PYTHON}", locate_mcp_python())
            config_text = config_text.replace("${AUGUR_ROOT}", PROJECT_ROOT.as_posix())
            config_text = config_text.replace("${AUGUR_CLIENT_ID}", "kimi")
            config = json.loads(config_text)

            if os.environ.get("AUGUR_SYNC_REPO_LOCAL_ONLY") == "1":
                return

            # Write to ~/.kimi/mcp.json
            target = Path.home() / ".kimi" / "mcp.json"
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

            target.write_text(json.dumps(config, indent=2), encoding="utf-8")
            logger.info(f"✅ Generated {target} (MCP config for Kimi)")

        except Exception as e:
            logger.error(f"Failed to generate MCP config for Kimi: {e}")

    def sync_memory(self) -> None:
        """Sync canonical memory to ~/.kimi/augur-memory.md (ADR-057)."""
        try:
            memory_content = self.get_projected_memory_content()
            if not memory_content:
                return
            target = Path.home() / ".kimi" / "augur-memory.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(memory_content, encoding="utf-8")
            logger.info(f"✅ Synced memory to {target}")
        except Exception as e:
            logger.error(f"Failed to sync memory for Kimi: {e}")
