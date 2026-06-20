"""Gemini formatter - produces Gemini CLI extension structure."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from .base import BaseFormatter
from .command_text import sanitize_packaged_skill_content, sanitize_project_router_content
from .mcp_config import build_augur_mcp_servers

logger = logging.getLogger(__name__)


class GeminiFormatter(BaseFormatter):
    """Format assembled plugin output as a Gemini CLI extension."""

    def plugin_dir(self, output_dir: Path) -> Path:
        return output_dir / "extensions" / "augur"

    def write_manifest(self, plugin_dir: Path, version: str) -> None:
        manifest = {
            "name": "augur",
            "version": version,
            "description": (
                "Your second brain -- personal knowledge, career, finance, "
                "health, and productivity powered by Augur"
            ),
            "contextFileName": "GEMINI.md",
        }
        (plugin_dir / "gemini-extension.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        context = """# Augur Extension

Augur is a local-first second brain exposed through the augur MCP server.

Use `/augur:ask` for reflective second-brain questions.
Use `/augur:discover` to inspect available Augur capabilities, commands, and system state.
Use `/augur:project` for current-folder project operations, including development workflows.
Use `/augur:routines` to list, run, report, and inspect recurring Augur routines.
Use `/augur:skillify` to turn durable incidents or gaps into reusable Augur skills.
"""
        (plugin_dir / "GEMINI.md").write_text(context, encoding="utf-8")

    def write_mcp_config(self, plugin_dir: Path, project_root: Path, python_path: str) -> None:
        manifest_path = plugin_dir / "gemini-extension.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {"name": "augur", "contextFileName": "GEMINI.md"}

        manifest["mcpServers"] = build_augur_mcp_servers(project_root, python_path, "gemini")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def write_marketplace(self, output_dir: Path, version: str) -> None:
        return None

    def write_skills(self, plugin_dir: Path, skills: dict[str, str]) -> None:
        for name, content in skills.items():
            skill_dir = plugin_dir / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                sanitize_packaged_skill_content(content),
                encoding="utf-8",
            )

    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        commands_dir = plugin_dir / "commands" / "augur"
        commands_dir.mkdir(parents=True, exist_ok=True)
        for name, cmd in commands.items():
            description = str(cmd["description"])
            body = str(cmd["body"])
            if name != "project":
                description = sanitize_packaged_skill_content(description)
                body = sanitize_packaged_skill_content(body)
            else:
                description = sanitize_project_router_content(description)
                body = sanitize_project_router_content(body)
            prompt = f"{body}\n\nUser arguments:\n{{{{args}}}}\n"
            content = (
                f"description = {json.dumps(description)}\n"
                f"prompt = {json.dumps(prompt)}\n"
            )
            (commands_dir / f"{name}.toml").write_text(content, encoding="utf-8")

    def install(
        self,
        output_dir: Path,
        version: str,
        *,
        extensions_dir: Path | None = None,
    ) -> bool:
        plugin_source = output_dir / "extensions" / "augur"
        if not plugin_source.exists():
            logger.warning("Gemini extension source not found at %s", plugin_source)
            return False

        if extensions_dir is None:
            extensions_dir = Path.home() / ".gemini" / "extensions"

        target = extensions_dir / "augur"
        if target.exists() or target.is_symlink():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(plugin_source, target)
        logger.info(
            "  Installed augur Gemini extension: %s. Restart Gemini CLI to load changes.",
            target,
        )
        return True
