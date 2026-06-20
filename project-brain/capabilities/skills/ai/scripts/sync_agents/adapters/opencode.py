"""sync_agents/adapters/opencode.py — OpenCode CLI adapter."""
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
    MCP_CONFIG_TEMPLATE,
    GENERATED_FILES,
    logger,
)
from ..engine import write_generated_file
from ..templates import global_mcp_project_root, locate_mcp_python, render_rules_projection


class OpenCodeAdapter(BaseAdapter):
    adapter_name = "opencode"

    def get_managed_files(self) -> list[str]:
        home = str(Path.home())
        return [
            ".opencode/AGENTS.md",
            ".opencode/skills/",
            f"{home}/.config/opencode/opencode.json",
        ]

    def get_state_files(self) -> list[str]:
        home = str(Path.home())
        return [
            f"{home}/.local/share/opencode/history/",
            f"{home}/.local/share/opencode/sessions/",
            f"{home}/.cache/opencode/",
        ]

    def detect_installed(self) -> bool:
        import shutil
        return shutil.which("opencode") is not None

    def distribute_external_skills(self, bundles: list) -> None:
        """Copy external skill bundles wholesale into ``.opencode/skills/`` (ADR-605)."""
        from ..external_skills import _distribute_via_file_copy
        target_root = PROJECT_ROOT / ".opencode" / "skills"
        _distribute_via_file_copy(
            bundles,
            adapter_name=self.adapter_name,
            target_root=target_root,
            label="OpenCode",
        )

    def sync_rules(self, content: str) -> None:
        resolved = render_rules_projection(content)
        write_generated_file(
            PROJECT_ROOT / ".opencode" / "AGENTS.md",
            resolved,
            source=SOURCE_RULES_LABEL,
        )

    def generate_mcp_config(self) -> None:
        """Generate resolved MCP config for OpenCode (~/.config/opencode/opencode.json)."""
        if not MCP_CONFIG_TEMPLATE.exists():
            logger.warning(f"MCP config template not found: {MCP_CONFIG_TEMPLATE}")
            return

        try:
            template_content = MCP_CONFIG_TEMPLATE.read_text(encoding="utf-8")

            identity = resolve_runtime_identity(PROJECT_ROOT)
            mcp_root = global_mcp_project_root(PROJECT_ROOT)
            # Resolve template variables.
            # locate_mcp_python() and mcp_root.as_posix() emit POSIX-style paths
            # so JSON serialization stays safe on Windows (no \U/\P escape errors).
            resolved = template_content.replace("${AUGUR_ROOT}", mcp_root.as_posix())

            resolved = resolved.replace("${AUGUR_PYTHON}", locate_mcp_python(mcp_root))
            resolved = resolved.replace("${AUGUR_CLIENT_ID}", "opencode")

            # Transform shared JSON-RPC template into OpenCode's config shape.
            template = json.loads(resolved)
            config = {
                "$schema": "https://opencode.ai/config.json",
                "mcp": {},
            }
            for server_name, server in template.get("mcpServers", {}).items():
                config["mcp"][server_name] = {
                    "type": "local",
                    "command": [server["command"], *server["args"]],
                    "enabled": True,
                    "environment": server["env"],
                    "timeout": 30000,
                }
            if os.environ.get("AUGUR_SYNC_REPO_LOCAL_ONLY") == "1":
                return

            target = Path.home() / ".config" / "opencode" / "opencode.json"
            target.parent.mkdir(parents=True, exist_ok=True)

            # Merge with existing config if present
            if target.exists():
                try:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                    if not isinstance(existing, dict):
                        existing = {}
                    existing.setdefault("$schema", "https://opencode.ai/config.json")
                    if "mcp" not in existing or not isinstance(existing["mcp"], dict):
                        existing["mcp"] = {}
                    for server_name in list(existing["mcp"]):
                        if server_name.startswith("augur"):
                            del existing["mcp"][server_name]
                    existing["mcp"].update(config["mcp"])
                    config = existing
                except (json.JSONDecodeError, OSError):
                    pass

            with GlobalIdentityLock(default_global_identity_lock_path()):
                with GlobalMutationGuard(
                    identity,
                    target_root=mcp_root,
                    operation="sync_agents:opencode-global",
                    allow_delegated=True,
                ):
                    target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            GENERATED_FILES.append(target)
            logger.info(f"✅ Generated {target} (MCP config for OpenCode)")
        except GlobalIdentityError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate MCP config for OpenCode: {e}")

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        """Remove managed files and surgically delete the augur OpenCode MCP entry."""
        deleted: list[str] = []
        excluded = {path.resolve() for path in (exclude_paths or set())}

        target = Path.home() / ".config" / "opencode" / "opencode.json"
        try:
            target_resolved = target.resolve()
        except OSError:
            target_resolved = target

        if target_resolved not in excluded and target.exists():
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
                mcp = data.get("mcp", {}) if isinstance(data, dict) else {}
                if isinstance(mcp, dict) and any(key.startswith("augur") for key in mcp):
                    deleted.append(str(target))
                    if not dry_run:
                        remaining = {
                            key: value
                            for key, value in mcp.items()
                            if not key.startswith("augur")
                        }
                        if remaining:
                            data["mcp"] = remaining
                            target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                            logger.info(f"Removed augur MCP entry from {target}")
                        else:
                            target.unlink()
                            logger.info(f"Deleted {target} (augur was only MCP entry)")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to clean opencode.json: {e}")

        base_paths = [path for path in self.get_managed_files() if "opencode.json" not in path]

        class _Delegate(BaseAdapter):
            def get_managed_files(self_inner) -> list[str]:
                return base_paths

        deleted.extend(_Delegate().cleanup(exclude_paths=exclude_paths, dry_run=dry_run))
        return deleted
