"""sync_agents/adapters/antigravity.py — Antigravity adapter."""
from __future__ import annotations
import json
import os
from pathlib import Path

from src.config.runtime_identity import (
    GlobalIdentityError,
    GlobalIdentityLock,
    GlobalMutationGuard,
    default_global_identity_lock_path,
    resolve_runtime_identity,
)

from .base import BaseAdapter
from ..constants import (
    PROJECT_ROOT,
    SOURCE_RULES_LABEL,
    SOURCE_TOPICS_LABEL,
    MCP_CONFIG_TEMPLATE,
    GENERATED_FILES,
    logger,
)
from ..engine import write_generated_file
from ..templates import global_mcp_project_root, locate_mcp_python, render_rules_projection



class AntigravityAdapter(BaseAdapter):
    adapter_name = "antigravity"

    _GLOBAL_MCP_CONFIG = Path.home() / ".gemini" / "antigravity" / "mcp_config.json"

    def get_state_files(self) -> list[str]:
        home = str(Path.home())
        return [
            f"{home}/.gemini/antigravity/brain/",
            f"{home}/.gemini/antigravity/code_tracker/",
        ]

    def get_managed_files(self) -> list[str]:
        return [
            ".antigravity/",
        ]

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        deleted: list[str] = []

        # Delete global mcp_config.json and all .bak siblings written by Antigravity
        mcp = self._GLOBAL_MCP_CONFIG
        if mcp.exists():
            deleted.append(str(mcp))
            if not dry_run:
                mcp.unlink()

        bak_files = sorted(mcp.parent.glob("mcp_config.json.bak.*")) if mcp.parent.exists() else []
        if bak_files:
            deleted.append(str(mcp.parent / "mcp_config.json.bak.*"))
            if not dry_run:
                for bak in bak_files:
                    bak.unlink()

        # Delegate local .antigravity/ cleanup to base
        deleted.extend(super().cleanup(exclude_paths=exclude_paths, dry_run=dry_run))
        return deleted

    def sync_topic_docs(self, content: str | None = None) -> None:
        """Sync topic docs to both docs/agent-topics/ and .antigravity/topics/ (ADR-096)."""
        # 1. Standard global sync
        super().sync_topic_docs(content)

        # 2. Antigravity-specific local sync for context
        self._sync_agent_topics(
            PROJECT_ROOT / ".antigravity" / "topics",
            SOURCE_TOPICS_LABEL
        )

    def detect_installed(self) -> bool:
        import shutil
        return shutil.which("antigravity") is not None or (Path.home() / ".gemini" / "antigravity").is_dir()

    def sync_rules(self, content: str) -> None:
        resolved = render_rules_projection(content)
        write_generated_file(
            PROJECT_ROOT / ".antigravity" / "instructions.md",
            resolved,
            source=SOURCE_RULES_LABEL,
        )

    def generate_mcp_config(self) -> None:
        """Generate resolved MCP config for Antigravity."""
        if not MCP_CONFIG_TEMPLATE.exists():
            logger.warning(f"MCP config template not found: {MCP_CONFIG_TEMPLATE}")
            return

        try:
            template_content = MCP_CONFIG_TEMPLATE.read_text(encoding="utf-8")

            def render_config(project_root: Path) -> dict:
                resolved = template_content.replace("${AUGUR_ROOT}", project_root.as_posix())
                resolved = resolved.replace("${AUGUR_PYTHON}", locate_mcp_python(project_root))
                resolved = resolved.replace("${AUGUR_CLIENT_ID}", "antigravity")
                return json.loads(resolved)

            targets: list[tuple[Path, Path, bool]] = [
                (PROJECT_ROOT / ".antigravity" / "mcp_config.json", PROJECT_ROOT, False),
            ]
            if os.environ.get("AUGUR_SYNC_REPO_LOCAL_ONLY") != "1":
                targets.append((self._GLOBAL_MCP_CONFIG, global_mcp_project_root(PROJECT_ROOT), True))

            identity = resolve_runtime_identity(PROJECT_ROOT)
            for target, target_root, preserve_existing in targets:
                config = render_config(target_root)
                if preserve_existing and target.exists():
                    try:
                        existing = json.loads(target.read_text(encoding="utf-8"))
                    except (OSError, ValueError, TypeError):
                        existing = {}
                    if isinstance(existing, dict):
                        servers = existing.get("mcpServers")
                        if not isinstance(servers, dict):
                            servers = {}
                            existing["mcpServers"] = servers
                        for server_name in list(servers):
                            if str(server_name).startswith("augur"):
                                del servers[server_name]
                        servers.update(config.get("mcpServers", {}))
                        config = existing
                target.parent.mkdir(parents=True, exist_ok=True)
                if preserve_existing:
                    with GlobalIdentityLock(default_global_identity_lock_path()):
                        with GlobalMutationGuard(
                            identity,
                            target_root=target_root,
                            operation="sync_agents:antigravity-global",
                            allow_delegated=True,
                        ):
                            target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
                else:
                    target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
                GENERATED_FILES.append(target)
                try:
                    display_path = target.relative_to(PROJECT_ROOT)
                except ValueError:
                    display_path = target
                logger.info(f"✅ Generated {display_path} (MCP config)")
        except GlobalIdentityError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate MCP config for Antigravity: {e}")
