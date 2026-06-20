"""Codex formatter — produces Codex plugin structure."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import yaml

from .base import BaseFormatter
from .command_text import sanitize_packaged_skill_content, sanitize_project_router_content
from .mcp_config import build_augur_mcp_config

logger = logging.getLogger(__name__)


class CodexFormatter(BaseFormatter):
    """Format assembled plugin for OpenAI Codex."""

    @staticmethod
    def _resolve_project_root(plugin_source: Path) -> Path | None:
        mcp_path = plugin_source / ".mcp.json"
        if not mcp_path.exists():
            return None
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {})
            if isinstance(servers, dict):
                for server_name in ("augur-framework", "augur-core", "augur"):
                    cwd = servers.get(server_name, {}).get("cwd")
                    if cwd:
                        return Path(cwd)
        except (OSError, json.JSONDecodeError, TypeError):
            return None
        return None

    def write_manifest(self, plugin_dir: Path, version: str) -> None:
        manifest = {
            "name": "augur",
            "version": version,
            "description": "Your second brain -- personal knowledge, career, finance, health, and productivity powered by Augur",
            "author": {"name": "Gur Sannikov"},
            "skills": "./skills/",
            "mcpServers": "./.mcp.json",
            "interface": {
                "displayName": "Augur",
                "shortDescription": "Personal knowledge system & second brain",
                "category": "Productivity",
                "capabilities": ["Read", "Write"],
            },
        }
        meta_dir = plugin_dir / ".codex-plugin"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    def write_mcp_config(self, plugin_dir: Path, project_root: Path, python_path: str) -> None:
        config = build_augur_mcp_config(project_root, python_path, "codex")
        (plugin_dir / ".mcp.json").write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

    def write_marketplace(self, output_dir: Path, version: str) -> None:
        marketplace = {
            "name": "augur-local",
            "interface": {"displayName": "Augur Local"},
            "plugins": [
                {
                    "name": "augur",
                    "source": {"source": "local", "path": "./plugins/augur"},
                    "policy": {
                        "installation": "INSTALLED_BY_DEFAULT",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Productivity",
                }
            ],
        }
        mp_dir = output_dir / ".agents" / "plugins"
        mp_dir.mkdir(parents=True, exist_ok=True)
        (mp_dir / "marketplace.json").write_text(
            json.dumps(marketplace, indent=2) + "\n", encoding="utf-8"
        )

    def write_skills(self, plugin_dir: Path, skills: dict[str, str]) -> None:
        for name, content in skills.items():
            skill_dir = plugin_dir / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                sanitize_packaged_skill_content(content),
                encoding="utf-8",
            )

    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        # Codex uses skills for commands — write as SKILL.md in skills/
        for name, cmd in commands.items():
            skill_dir = plugin_dir / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            description = str(cmd["description"])
            body = str(cmd["body"])
            if name != "project":
                description = sanitize_packaged_skill_content(description)
                body = sanitize_packaged_skill_content(body)
            else:
                description = sanitize_project_router_content(description)
                body = sanitize_project_router_content(body)
            frontmatter = yaml.safe_dump(
                {"name": name, "description": description},
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            ).rstrip("\n")
            content = f"---\n{frontmatter}\n---\n\n{body}\n"
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def install(
        self,
        output_dir: Path,
        version: str,
        *,
        cache_dir: Path | None = None,
        global_marketplace_dir: Path | None = None,
    ) -> bool:
        """Install plugin to repo-local Codex cache and marketplace by default."""

        plugin_source = output_dir / "plugins" / "augur"
        if not plugin_source.exists():
            logger.warning("Plugin source not found at %s", plugin_source)
            return False

        project_root = self._resolve_project_root(plugin_source)
        if cache_dir is None:
            cache_dir = (
                project_root / ".codex" / "plugins" / "cache"
                if project_root is not None
                else Path.home() / ".codex" / "plugins" / "cache"
            )
        if global_marketplace_dir is None:
            global_marketplace_dir = (
                project_root / ".agents" / "plugins"
                if project_root is not None
                else Path.home() / ".agents" / "plugins"
            )

        # Copy to cache. The augur-local/augur subtree is sync-managed; remove
        # stale sibling versions so Codex cannot discover retired MCP bundles
        # from an older cached plugin.
        cache_root = cache_dir / "augur-local" / "augur"
        if cache_root.exists():
            for child in cache_root.iterdir():
                if child.name == version:
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()

        cache_target = cache_root / version
        if cache_target.exists():
            shutil.rmtree(cache_target)
        cache_target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(plugin_source, cache_target, dirs_exist_ok=True)
        logger.info("  Installed augur to Codex cache: %s", cache_target)

        # Repo-local marketplace lives at <root>/.agents/plugins/marketplace.json
        # and points to ./plugins/<plugin-name> from the repo root.
        install_root = global_marketplace_dir.parent.parent
        local_plugin_dir = install_root / "plugins" / "augur"
        if local_plugin_dir.exists() or local_plugin_dir.is_symlink():
            if local_plugin_dir.is_dir() and not local_plugin_dir.is_symlink():
                shutil.rmtree(local_plugin_dir)
            else:
                local_plugin_dir.unlink()
        shutil.copytree(plugin_source, local_plugin_dir, dirs_exist_ok=True)
        logger.info("  Installed augur beside marketplace: %s", local_plugin_dir)

        # Write/merge global marketplace
        global_marketplace_dir.mkdir(parents=True, exist_ok=True)
        mp_path = global_marketplace_dir / "marketplace.json"

        augur_entry = {
            "name": "augur",
            "source": {"source": "local", "path": "./plugins/augur"},
            "policy": {
                "installation": "INSTALLED_BY_DEFAULT",
                "authentication": "ON_INSTALL",
            },
            "category": "Productivity",
        }

        if mp_path.exists():
            try:
                existing = json.loads(mp_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = None
        else:
            existing = None

        if existing and isinstance(existing.get("plugins"), list):
            plugins = [p for p in existing["plugins"] if p.get("name") != "augur"]
            plugins.append(augur_entry)
            existing["plugins"] = plugins
            marketplace = existing
        else:
            marketplace = {
                "name": "augur-local",
                "interface": {"displayName": "Augur Local"},
                "plugins": [augur_entry],
            }

        mp_path.write_text(json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")
        logger.info("  Updated global marketplace: %s", mp_path)

        return True
