"""IDE Integration Pillars - Check status of Skills, MCP, Hooks, Slash Commands, etc."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import warnings

from src.config.paths import get_project_root


class PillarChecker:
    """Checks status of Augur integration pillars for each IDE."""

    def __init__(self):
        self.project_root = get_project_root()
        self.data_base = get_project_root()

    def check_skills_pillar(self, ide_name: str) -> dict[str, Any]:
        """
        Check Skills pillar: Are skills discoverable and accessible?

        Returns:
            dict with status, config_paths, and details
        """
        skills_dir = self.project_root / "plugins"
        skills_exist = skills_dir.exists() and any(skills_dir.iterdir())

        # Check for skill registry or discovery mechanism
        skill_registry_path = self.project_root / "src/lib" / "mcp" / "dynamic_registry.py"
        registry_exists = skill_registry_path.exists()

        # Check for SKILL.md files
        skill_files = list(skills_dir.rglob("SKILL.md"))

        return {
            "status": "healthy" if (skills_exist and registry_exists) else "degraded",
            "config_paths": [
                str(skills_dir),
                str(skill_registry_path) if registry_exists else None,
            ],
            "details": {
                "skills_dir_exists": skills_exist,
                "registry_exists": registry_exists,
                "skill_count": len(skill_files),
            },
            "config_files": {
                "skills_directory": str(skills_dir),
                "skill_registry": str(skill_registry_path) if registry_exists else None,
            },
        }

    def check_mcp_pillar(self, ide_name: str) -> dict[str, Any]:
        """
        Check MCP pillar: Is MCP server configured and accessible?

        Returns:
            dict with status, config_paths, and details
        """
        # Check MCP server code
        mcp_server_path = self.project_root / "src" / "mcp" / "augur_framework" / "__main__.py"

        mcp_exists = mcp_server_path.exists()

        # Check IDE-specific MCP config
        config_paths = {}
        if ide_name == "cursor":
            cursor_config = Path.home() / ".cursor" / "mcp.json"
            config_paths["cursor_mcp_config"] = str(cursor_config) if cursor_config.exists() else None
        elif ide_name == "vscode_copilot":
            # VS Code MCP config location (when supported)
            vscode_config = Path.home() / ".vscode" / "mcp.json"
            config_paths["vscode_mcp_config"] = str(vscode_config) if vscode_config.exists() else None
        elif ide_name in {"codex", "codex_cli"}:
            codex_config = Path.home() / ".codex" / "config.toml"
            config_paths["codex_config"] = str(codex_config) if codex_config.exists() else None
        elif ide_name == "claude_desktop":
            claude_config = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            config_paths["claude_mcp_config"] = str(claude_config) if claude_config.exists() else None
        elif ide_name == "claude_code":
            claude_code_config = Path.home() / ".claude.json"
            config_paths["claude_code_config"] = str(claude_code_config) if claude_code_config.exists() else None

        # Check if MCP server can be imported
        mcp_importable = False
        try:
            import sys

            sys.path.insert(0, str(self.project_root))
            mcp_importable = True
        except Exception as e:
            warnings.warn(
                f"Unable to set import path for MCP check: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

        return {
            "status": "healthy" if (mcp_exists and mcp_importable) else "degraded",
            "config_paths": [str(mcp_server_path)] + [p for p in config_paths.values() if p],
            "details": {
                "mcp_server_exists": mcp_exists,
                "mcp_importable": mcp_importable,
                "ide_config_configured": any(config_paths.values()),
            },
            "config_files": {
                "mcp_server": str(mcp_server_path),
                **config_paths,
            },
        }

    def check_hooks_pillar(self, ide_name: str) -> dict[str, Any]:
        """
        Check Hooks pillar: Are lifecycle hooks configured?

        Returns:
            dict with status, config_paths, and details
        """
        # Check for CI hooks
        ci_workflows = self.project_root / ".github" / "workflows"
        ci_exists = ci_workflows.exists() and any(ci_workflows.glob("*.yml"))

        # Check for adaptive growth hooks
        adaptive_growth_path = (
            self.project_root
            / "plugins"
            / "factory-core"
            / "skills"
            / "devops"
            / "services"
            / "setup_manager"
            / "analyzers.py"
        )
        adaptive_growth_exists = adaptive_growth_path.exists()

        # Check for retrospective hooks
        retrospective_path = self.project_root / "src/lib" / "modules" / "retrospective.py"
        retrospective_exists = retrospective_path.exists()

        return {
            "status": "healthy" if (ci_exists or adaptive_growth_exists) else "degraded",
            "config_paths": [
                str(ci_workflows) if ci_exists else None,
                str(adaptive_growth_path) if adaptive_growth_exists else None,
                str(retrospective_path) if retrospective_exists else None,
            ],
            "details": {
                "ci_hooks": ci_exists,
                "adaptive_growth": adaptive_growth_exists,
                "retrospective": retrospective_exists,
            },
            "config_files": {
                "ci_workflows": str(ci_workflows) if ci_exists else None,
                "adaptive_growth": str(adaptive_growth_path) if adaptive_growth_exists else None,
                "retrospective": str(retrospective_path) if retrospective_exists else None,
            },
        }

    def check_slash_commands_pillar(self, ide_name: str) -> dict[str, Any]:
        """
        Check Slash Commands pillar: Are slash commands configured?

        Returns:
            dict with status, config_paths, and details
        """
        # Check for command parser
        ide_commands_path = self.project_root / "src/lib" / "llm" / "ide_commands.py"
        commands_exist = ide_commands_path.exists()

        # Check for workflow definitions
        workflows_dir = self.project_root / ".antigravity" / "workflows"
        workflows_exist = workflows_dir.exists() if workflows_dir else False

        # Check for instruction generator
        instruction_gen_path = self.project_root / "src/lib" / "llm" / "instruction_generator.py"
        instruction_gen_exists = instruction_gen_path.exists()

        return {
            "status": "healthy" if (commands_exist and instruction_gen_exists) else "degraded",
            "config_paths": [
                str(ide_commands_path) if commands_exist else None,
                str(workflows_dir) if workflows_exist else None,
                str(instruction_gen_path) if instruction_gen_exists else None,
            ],
            "details": {
                "command_parser": commands_exist,
                "workflows": workflows_exist,
                "instruction_generator": instruction_gen_exists,
            },
            "config_files": {
                "ide_commands": str(ide_commands_path) if commands_exist else None,
                "workflows": str(workflows_dir) if workflows_exist else None,
                "instruction_generator": str(instruction_gen_path) if instruction_gen_exists else None,
            },
        }

    def check_agents_pillar(self, ide_name: str) -> dict[str, Any]:
        """
        Check Agents pillar: Are agents orchestrated and accessible?

        Returns:
            dict with status, config_paths, and details
        """
        agents_dir = self.project_root / "plugins" / "agents"
        registry_path = agents_dir / "registry.json"
        registry_exists = registry_path.exists()

        agent_files = []
        if agents_dir.exists():
            agent_files = [p for p in agents_dir.glob("*.md") if p.name.lower() != "readme.md"]

        # Check for MCP agent tools
        mcp_server_path = self.project_root / "src" / "mcp" / "augur_framework" / "__main__.py"
        mcp_has_agents = False
        if mcp_server_path.exists():
            try:
                content = mcp_server_path.read_text()
                mcp_has_agents = "agent" in content.lower() or "skill" in content.lower()
            except Exception as e:
                warnings.warn(
                    f"Unable to inspect MCP server file {mcp_server_path}: {e}",
                    RuntimeWarning,
                    stacklevel=2,
                )

        return {
            "status": "healthy" if (registry_exists and len(agent_files) > 0) else "degraded",
            "config_paths": [
                str(registry_path) if registry_exists else None,
                str(agents_dir) if agents_dir.exists() else None,
            ],
            "details": {
                "agent_registry_exists": registry_exists,
                "agent_count": len(agent_files),
                "mcp_exposes_agents": mcp_has_agents,
            },
            "config_files": {
                "agent_registry": str(registry_path) if registry_exists else None,
                "agent_definitions": [str(p) for p in agent_files],
            },
        }

    def check_local_remote_pillar(self, ide_name: str) -> dict[str, Any]:
        """
        Check Local/Remote Coding pillar: Is hybrid execution configured?

        Returns:
            dict with status, config_paths, and details
        """
        # Check for CLI interface
        cli_path = self.project_root / "augur_api.py"
        cli_exists = cli_path.exists()

        # Check for MCP (enables remote)
        mcp_server_path = self.project_root / "src/lib" / "mcp" / "server.py"
        mcp_exists = mcp_server_path.exists()

        # Check for bridge scripts
        bridge_path = self.project_root / "src/lib" / "scripts" / "ide_bridge.py"
        bridge_exists = bridge_path.exists()

        return {
            "status": "healthy" if (cli_exists or mcp_exists) else "degraded",
            "config_paths": [
                str(cli_path) if cli_exists else None,
                str(mcp_server_path) if mcp_exists else None,
                str(bridge_path) if bridge_exists else None,
            ],
            "details": {
                "cli_interface": cli_exists,
                "mcp_server": mcp_exists,
                "bridge_scripts": bridge_exists,
            },
            "config_files": {
                "cli": str(cli_path) if cli_exists else None,
                "mcp_server": str(mcp_server_path) if mcp_exists else None,
                "bridge": str(bridge_path) if bridge_exists else None,
            },
        }

    def check_instructions_pillar(self, ide_name: str) -> dict[str, Any]:
        """
        Check Instructions pillar: Are native instructions generated and available?

        Returns:
            dict with status, config_paths, and details
        """
        # Map IDEs to their instruction files
        ide_key = ide_name.lower().replace(" ", "")

        instruction_map = {
            "cursor": [".cursor/rules/augur.mdc"],
            "antigravity": [".antigravity/instructions.md", "CLAUDE.md"],
            "claudedesktop": ["CLAUDE.md"],
            "claude_desktop": ["CLAUDE.md"],
            "claude_code": ["CLAUDE.md"],
            "claude": ["CLAUDE.md"],
            "codex": ["CODEX.md", ".github/copilot-instructions.md"],
            "vscode": [".vscode/augur-instructions.md", ".github/copilot-instructions.md"],
            "vscode_copilot": [".vscode/augur-instructions.md", ".github/copilot-instructions.md"],
        }

        target_files = instruction_map.get(ide_key, [])
        if not target_files:
            # Fallback for unknown IDEs -> check generic CLAUDE.md
            target_files = ["CLAUDE.md"]

        config_files: dict[str, Optional[str]] = {}
        all_exist = True

        for file_rel_path in target_files:
            file_path = self.project_root / file_rel_path
            if file_path.exists():
                config_files[file_rel_path] = str(file_path)
            else:
                all_exist = False
                config_files[file_rel_path] = None

        return {
            "status": "healthy" if (all_exist and len(config_files) > 0) else "degraded",
            "config_paths": [v for v in config_files.values() if v],
            "details": {
                "files_checked": target_files,
                "all_exist": all_exist,
                "missing": [k for k, v in config_files.items() if v is None],
            },
            "config_files": config_files,
        }

    def check_all_pillars(self, ide_name: str) -> dict[str, Any]:
        """
        Check all pillars for an IDE.

        Returns:
            dict with pillar names as keys, each containing status, config_paths, details, config_files
        """
        return {
            "skills": self.check_skills_pillar(ide_name),
            "mcp": self.check_mcp_pillar(ide_name),
            "hooks": self.check_hooks_pillar(ide_name),
            "slash_commands": self.check_slash_commands_pillar(ide_name),
            "agents": self.check_agents_pillar(ide_name),
            "local_remote": self.check_local_remote_pillar(ide_name),
            "instructions": self.check_instructions_pillar(ide_name),
        }


def get_pillar_status(ide_name: str) -> dict[str, Any]:
    """Get pillar status for an IDE."""
    checker = PillarChecker()
    return checker.check_all_pillars(ide_name)
