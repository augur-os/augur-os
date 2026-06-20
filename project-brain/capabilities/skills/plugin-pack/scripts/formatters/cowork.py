"""Cowork formatter — produces Claude Desktop plugin structure."""
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
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.config.runtime_identity import global_mcp_project_root

from .base import BaseFormatter
from .cloud_staleness import check_cloud_plugin_staleness
from .mcp_config import (
    build_augur_mcp_config,
    build_augur_mcp_servers,
    prune_augur_servers,
    resolve_project_python_path,
)

logger = logging.getLogger(__name__)


class CoworkFormatter(BaseFormatter):
    """Format assembled plugin for Claude Desktop (Cowork)."""

    def write_manifest(self, plugin_dir: Path, version: str) -> None:
        manifest = {
            "name": "augur",
            "description": "Your second brain -- personal knowledge, career, finance, health, and productivity powered by Augur",
            "version": version,
            "author": {"name": "Gur Sannikov"},
        }
        meta_dir = plugin_dir / ".claude-plugin"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    def write_mcp_config(self, plugin_dir: Path, project_root: Path, python_path: str) -> None:
        config = build_augur_mcp_config(project_root, python_path, "cowork")
        (plugin_dir / ".mcp.json").write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

    def write_marketplace(self, output_dir: Path, version: str) -> None:
        marketplace = {
            "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
            "name": "augur-cowork",
            "description": "Augur personal knowledge system plugins for Claude Cowork",
            "owner": {"name": "Gur Sannikov"},
            "plugins": [
                {
                    "name": "augur",
                    "description": "Your second brain -- personal knowledge, career, finance, health, and productivity powered by Augur",
                    "version": version,
                    "author": {"name": "Gur Sannikov"},
                    "source": "./plugins/augur",
                }
            ],
        }
        mp_dir = output_dir / ".claude-plugin"
        mp_dir.mkdir(parents=True, exist_ok=True)
        (mp_dir / "marketplace.json").write_text(
            json.dumps(marketplace, indent=2) + "\n", encoding="utf-8"
        )

    def write_skills(self, plugin_dir: Path, skills: dict[str, str]) -> None:
        for name, content in skills.items():
            skill_dir = plugin_dir / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        commands_dir = plugin_dir / "commands"
        if not commands:
            if commands_dir.exists():
                shutil.rmtree(commands_dir)
            return

        commands_dir.mkdir(parents=True, exist_ok=True)
        for name, cmd in commands.items():
            content = f"---\nname: {name}\ndescription: {cmd['description']}\n---\n\n{cmd['body']}\n"
            (commands_dir / f"{name}.md").write_text(content, encoding="utf-8")

    def install(self, output_dir: Path, version: str) -> bool:
        """Install to Claude Desktop's local-desktop-app-uploads."""
        cowork_dir = _find_cowork_plugin_dir()
        if not cowork_dir:
            logger.info("  Cowork not detected, skipping desktop install")
            return False

        uploads_dir = cowork_dir / "marketplaces" / "local-desktop-app-uploads"
        if not uploads_dir.exists():
            logger.info("  Cowork local-desktop-app-uploads not found, skipping")
            return False

        plugin_dir = output_dir / "plugins" / "augur"
        target = uploads_dir / "augur"

        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(plugin_dir, target)

        # Register in installed_plugins.json
        installed_path = cowork_dir / "installed_plugins.json"
        if installed_path.exists():
            try:
                installed = json.loads(installed_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                installed = {"version": 2, "plugins": {}}
        else:
            installed = {"version": 2, "plugins": {}}

        now = datetime.now(timezone.utc).isoformat()
        key = "augur@local-desktop-app-uploads"
        existing = installed.get("plugins", {}).get(key, [{}])
        installed["plugins"][key] = [{
            "scope": "user",
            "installPath": str(target),
            "version": version,
            "installedAt": existing[0].get("installedAt", now) if existing else now,
            "lastUpdated": now,
        }]

        installed_path.write_text(json.dumps(installed, indent=2) + "\n", encoding="utf-8")

        # Register MCP server in claude_desktop_config.json
        _register_mcp_connector(output_dir)

        logger.info("  Installed augur to Cowork desktop")

        # Local install covers Cowork agent sessions ONLY. Regular Desktop
        # chats serve the claude.ai cloud copy — warn loudly if it has drifted
        # so "Installed" can never again mask a stale user-facing surface.
        report = check_cloud_plugin_staleness(plugin_dir)
        if report["checked"] and report["stale"]:
            logger.warning(
                "  CLOUD PLUGIN STALE — regular Claude Desktop chats serve an "
                "outdated Augur plugin (uploaded %s at %s):",
                report["cloud_updated_at"],
                report["rpm_dir"],
            )
            for reason in report["reasons"]:
                logger.warning("    - %s", reason)
            logger.warning(
                "    Fix: re-upload the bundle to claude.ai My Uploads "
                "(account-upload endpoint; see plugin-pack SKILL.md)."
            )
        return True


def _find_cowork_plugin_dir() -> Path | None:
    """Find Cowork's cowork_plugins directory inside Claude Desktop app data."""
    base = Path.home() / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"
    if not base.exists():
        return None
    for session_dir in base.iterdir():
        if not session_dir.is_dir():
            continue
        for org_dir in session_dir.iterdir():
            if not org_dir.is_dir():
                continue
            candidate = org_dir / "cowork_plugins"
            if candidate.exists():
                return candidate
    return None


def _register_mcp_connector(output_dir: Path) -> None:
    """Register Augur MCP server in claude_desktop_config.json."""
    from src.config.paths import get_project_root

    project_root = global_mcp_project_root(Path(get_project_root()))
    config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if not config_path.exists():
        return

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    python_path = resolve_project_python_path(project_root)

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    existing_server_ids = {
        str(server_id)
        for server_id in config["mcpServers"]
        if str(server_id).startswith("augur")
    }
    prune_augur_servers(config["mcpServers"])
    config["mcpServers"].update(
        build_augur_mcp_servers(
            project_root,
            python_path,
            "cowork",
            existing_server_ids=existing_server_ids,
        )
    )
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    logger.info("  Registered Augur MCP connector in claude_desktop_config.json")
