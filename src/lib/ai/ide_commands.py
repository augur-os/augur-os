"""IDE Command System - /command syntax for IDE execution."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .ide_backlog import save_instruction
from .instruction_generator import InstructionGenerator


@dataclass
class Command:
    """Parsed IDE command."""

    command: str
    params: dict[str, Any]
    ide: str | None = None


class IDECommandParser:
    """Parses /command syntax from IDE input."""

    # Command patterns
    COMMANDS = {
        "create-skill": {
            "action": "create_skill",
            "params": ["name", "patterns", "layer", "title"],
        },
        "analyze-skill": {
            "action": "analyze_skill",
            "params": ["skill_path"],
        },
        "generate-dashboard": {
            "action": "generate_dashboard",
            "params": ["skill_name"],
        },
        "help": {
            "action": "help",
            "params": [],
        },
        "run-investor-demo": {
            "action": "run_investor_demo",
            "params": [],
        },
    }

    def parse(self, text: str, ide: str | None = None) -> Command | None:
        """Parse command from text."""
        # Look for /command pattern
        match = re.match(r"/([\w-]+)(?:\s+(.+))?$", text.strip())
        if not match:
            return None

        cmd_name = match.group(1).lower()
        args_text = match.group(2) or ""

        if cmd_name not in self.COMMANDS:
            return None

        cmd_def = self.COMMANDS[cmd_name]
        params = self._parse_params(args_text, cmd_def["params"])

        return Command(
            command=cmd_name,
            params=params,
            ide=ide,
        )

    def _parse_params(self, args_text: str, param_names: list[str]) -> dict[str, Any]:
        """Parse parameters from command arguments."""
        params: dict[str, Any] = {}

        # Try JSON first
        if args_text.strip().startswith("{"):
            try:
                return json.loads(args_text)
            except json.JSONDecodeError:
                pass

        # Parse key=value pairs
        for part in args_text.split():
            if "=" in part:
                key, value = part.split("=", 1)
                if key in param_names:
                    # Try to parse value
                    if value.lower() in ("true", "false"):
                        params[key] = value.lower() == "true"
                    elif value.isdigit():
                        params[key] = int(value)
                    else:
                        params[key] = value

        # If no key=value, treat as positional arguments
        if not params and args_text.strip():
            parts = args_text.strip().split()
            for i, param_name in enumerate(param_names):
                if i < len(parts):
                    params[param_name] = parts[i]

        return params

    def get_help(self) -> str:
        """Get help text for available commands."""
        help_lines = ["# Augur IDE Commands\n"]
        help_lines.append("Available commands:\n")

        for cmd_name, cmd_def in self.COMMANDS.items():
            help_lines.append(f"## /{cmd_name}")
            help_lines.append(f"Action: {cmd_def['action']}")
            if cmd_def["params"]:
                help_lines.append(f"Parameters: {', '.join(cmd_def['params'])}")
            help_lines.append("")

        help_lines.append("## Examples")
        help_lines.append("```")
        help_lines.append("/create-skill name=expense-tracker patterns=inbox,database")
        help_lines.append("/analyze-skill skill_path=project-brain/capabilities/skills/knowledge")
        help_lines.append("/generate-dashboard skill_name=expense-tracker")
        help_lines.append("```")

        return "\n".join(help_lines)


class IDECommandExecutor:
    """Executes IDE commands and saves instructions."""

    def __init__(self):
        self.parser = IDECommandParser()
        self.generator = InstructionGenerator()

    def execute(self, command_text: str, ide: str | None = None) -> dict[str, Any]:
        """Execute a command and return result."""
        # Parse command
        command = self.parser.parse(command_text, ide)
        if not command:
            return {
                "success": False,
                "error": "Unknown command. Use /help for available commands.",
            }

        # Handle help command
        if command.command == "help":
            help_text = self.parser.get_help()
            return {
                "success": True,
                "content": help_text,
                "filename": "augur-commands-help.md",
            }

        # Get command definition
        cmd_def = self.parser.COMMANDS[command.command]
        action = cmd_def["action"]

        # Generate instruction
        try:
            if ide == "cursor" or not ide:
                instruction = self.generator.generate_cursor_instructions(action, command.params)
            elif ide == "copilot":
                instruction = self.generator.generate_copilot_instructions(action, command.params)
            elif ide == "antigravity":
                instruction = self.generator.generate_antigravity_workflow(action, command.params)
            else:
                instruction = self.generator.generate_cursor_instructions(action, command.params)

            # Save to backlog
            if ide == "antigravity":
                # Save to project-specific .antigravity/workflows directory
                from src.config.paths import get_project_root

                workflows_dir = get_project_root() / ".antigravity" / "workflows"
                workflows_dir.mkdir(parents=True, exist_ok=True)

                file_path = workflows_dir / (instruction.filename or f"antigravity-{action}.md")
                file_path.write_text(instruction.content, encoding="utf-8")
            else:
                file_path = save_instruction(
                    ide=ide or "cursor",
                    action=action,
                    content=instruction.content,
                    params=command.params,
                    filename=instruction.filename,
                )

            return {
                "success": True,
                "content": instruction.content,
                "filename": instruction.filename or file_path.name,
                "path": str(file_path),
                "description": instruction.description,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to execute command: {str(e)}",
            }


def execute_command(command_text: str, ide: str | None = None) -> dict[str, Any]:
    """Convenience function to execute a command."""
    executor = IDECommandExecutor()
    return executor.execute(command_text, ide)
