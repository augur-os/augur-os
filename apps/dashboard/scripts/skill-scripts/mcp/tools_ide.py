"""IDE integration tools for mcp-app-factory.

Tools: skill-generate, command-execute, backlog-list, backlog-read,
       skill-analyze, generate-ide-instructions
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._helpers import (
    logger,
    tool_annotations,
    get_project_root,
    get_ide_backlog_manager,
    get_ide_command_executor,
    get_instruction_generator,
    ai_required_error,
    get_project_root_local,
)


# ============================================================================
# Implementation Functions
# ============================================================================


async def skill_generate_impl(
    name: str, patterns: list[str], layer: str = "vertical", title: str | None = None
) -> dict:
    """Generate a new Augur skill via instruction file."""
    InstructionGenerator = get_instruction_generator()
    backlog_mgr = get_ide_backlog_manager()

    if InstructionGenerator is None or backlog_mgr is None:
        return json.loads(ai_required_error("skill_generate"))

    try:
        if not name or not patterns:
            return {"success": False, "error": f"name and patterns are required. Got name={name}, patterns={patterns}"}

        title = title or name.replace("-", " ").title()

        generator = InstructionGenerator()
        instruction = generator.generate_cursor_instructions(
            "create_skill",
            {"name": name, "patterns": patterns, "layer": layer, "title": title},
        )

        backlog_mgr["get_dir"]()
        file_path = backlog_mgr["save"](
            ide="cursor",
            action="create_skill",
            content=instruction.content,
            params={"name": name, "patterns": patterns, "layer": layer, "title": title},
            filename=instruction.filename,
        )

        return {
            "success": True,
            "skill": title,
            "name": name,
            "patterns": patterns,
            "layer": layer,
            "instruction_path": str(file_path),
            "content_preview": (
                instruction.content[:500] + "..." if len(instruction.content) > 500 else instruction.content
            ),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def command_execute_impl(command: str, ide: str = "cursor") -> dict:
    """Execute an Augur command."""
    execute_command = get_ide_command_executor()

    if execute_command is None:
        return json.loads(ai_required_error("command_execute"))

    try:
        if not command:
            return {"success": False, "error": "command is required"}

        result = execute_command(command, ide)

        if result.get("success"):
            return {
                "success": True,
                "command": command,
                "ide": ide,
                "path": result.get("path", "ide-backlog folder"),
                "content": result.get("content", ""),
            }
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def backlog_list_impl(ide: str | None = None, limit: int = 50) -> dict:
    """List instructions in the IDE backlog folder."""
    backlog_mgr = get_ide_backlog_manager()

    if backlog_mgr is None:
        return {"success": True, "count": 0, "instructions": [], "standalone_mode": True}

    try:
        instructions = backlog_mgr["list"](ide=ide, limit=limit)

        if not instructions:
            return {"success": True, "count": 0, "instructions": []}

        return {"success": True, "count": len(instructions), "instructions": instructions[:50]}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def backlog_read_impl(filename: str) -> dict:
    """Read a specific instruction from the backlog."""
    backlog_mgr = get_ide_backlog_manager()

    if backlog_mgr is None:
        return json.loads(ai_required_error("backlog_read"))

    try:
        if not filename:
            return {"success": False, "error": "filename is required"}

        backlog_dir = backlog_mgr["get_dir"]()
        file_path = backlog_dir / filename

        if not file_path.exists():
            return {"success": False, "error": f"File not found: {filename}"}

        content = file_path.read_text(encoding="utf-8")
        return {"success": True, "filename": filename, "content": content}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def skill_analyze_impl(skill_path: str) -> dict:
    """Analyze an existing Augur skill for review/refactoring."""
    InstructionGenerator = get_instruction_generator()
    backlog_mgr = get_ide_backlog_manager()

    if InstructionGenerator is None or backlog_mgr is None:
        return json.loads(ai_required_error("skill_analyze"))

    try:
        if not skill_path:
            return {"success": False, "error": "skill_path is required"}

        project_root = get_project_root_local()
        path = Path(skill_path)
        if not path.is_absolute():
            path = project_root / skill_path

        if not path.exists():
            return {"success": False, "error": f"Skill path does not exist: {skill_path}", "tried": str(path)}

        generator = InstructionGenerator()
        instruction = generator.generate_cursor_instructions(
            "analyze_skill",
            {"skill_path": str(path)},
        )

        file_path = backlog_mgr["save"](
            ide="cursor",
            action="review_refactor_skill",
            content=instruction.content,
            params={"skill_path": str(path)},
            filename=instruction.filename,
        )

        return {
            "success": True,
            "skill": path.name,
            "path": str(path),
            "instruction_path": str(file_path),
            "content_preview": (
                instruction.content[:500] + "..." if len(instruction.content) > 500 else instruction.content
            ),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Tool Registration
# ============================================================================


def register_ide_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register IDE integration tools with the MCP server."""

    @mcp.tool(
        name="skill-generate",
        annotations=tool_annotations(
            {
                "title": "Generate Skill",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def skill_generate_tool(
        name: str,
        patterns: list[str],
        layer: str = "vertical",
        title: str | None = None,
    ) -> str:
        """Generate a new Augur skill with specified patterns.

        Creates an instruction file in the IDE backlog for skill generation.

        Args:
            name: Skill name (kebab-case)
            patterns: Skill patterns (e.g., inbox, database, dashboard)
            layer: Skill layer (vertical, horizontal, factory)
            title: Skill title (defaults to formatted name)

        Returns:
            str: JSON with skill info and instruction path
        """
        metrics.track_tool("skill_generate", skill="mcp-app-factory", skill_name=name)
        result = await skill_generate_impl(name, patterns, layer, title)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="command-execute",
        annotations=tool_annotations(
            {
                "title": "Execute Command",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def command_execute_tool(command: str, ide: str = "cursor") -> str:
        """Execute an Augur command (e.g., /create-skill name=my-skill).

        Args:
            command: Command to execute
            ide: Target IDE (cursor, copilot, antigravity)

        Returns:
            str: JSON with execution result
        """
        metrics.track_tool("command_execute", skill="mcp-app-factory")
        result = await command_execute_impl(command, ide)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="backlog-list",
        annotations=tool_annotations(
            {
                "title": "List Backlog",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def backlog_list_tool(ide: str | None = None, limit: int = 50) -> str:
        """List instructions in the IDE backlog folder.

        Args:
            ide: Filter by IDE (optional)
            limit: Maximum number of instructions to return

        Returns:
            str: JSON with list of instructions
        """
        metrics.track_tool("backlog_list", skill="mcp-app-factory")
        result = await backlog_list_impl(ide, limit)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="backlog-read",
        annotations=tool_annotations(
            {
                "title": "Read Backlog Item",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def backlog_read_tool(filename: str) -> str:
        """Read a specific instruction from the backlog.

        Args:
            filename: Instruction filename

        Returns:
            str: JSON with instruction content
        """
        metrics.track_tool("backlog_read", skill="mcp-app-factory")
        result = await backlog_read_impl(filename)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="skill-analyze",
        annotations=tool_annotations(
            {
                "title": "Analyze Skill",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def skill_analyze_tool(skill_path: str) -> str:
        """Analyze an existing Augur skill for review and refactoring.

        Creates an instruction file for comprehensive skill analysis.

        Args:
            skill_path: Path to skill directory

        Returns:
            str: JSON with analysis info and instruction path
        """
        metrics.track_tool("skill_analyze", skill="mcp-app-factory")
        result = await skill_analyze_impl(skill_path)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="generate-ide-instructions",
        annotations=tool_annotations(
            {
                "title": "Generate IDE Instructions",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def generate_ide_instructions_tool(
        action: str,
        ide: str = "cursor",
        params: dict | None = None,
        save_to_backlog: bool = True,
    ) -> str:
        """Generate IDE-specific instructions for actions like skill creation.

        Creates instructions formatted for Cursor, GitHub Copilot, or Antigravity,
        enabling agents to self-generate IDE workflows.

        Args:
            action: Action type (create_skill, refactor, analyze, etc.)
            ide: Target IDE (cursor, copilot, antigravity)
            params: Action-specific parameters
            save_to_backlog: Whether to save instruction to IDE backlog

        Returns:
            str: JSON with generated instruction content and file path
        """
        metrics.track_tool("generate_ide_instructions", skill="mcp-app-factory")

        try:
            action_params = params or {}
            name = action_params.get("name", "new-skill")
            patterns = action_params.get("patterns", [])

            # Generate instructions based on IDE
            if ide == "cursor":
                content = f"""# Cursor Instructions: {action}

## Run in Cursor Chat
Press `Cmd+L` (Mac) or `Ctrl+L` (Windows/Linux) and run:

```
{f'Create a new Augur skill called "{name}" with patterns: {", ".join(patterns) or "basic"}' if action == 'create_skill' else f'{action}: {json.dumps(action_params)}'}
```

Cursor will generate the necessary files following Augur conventions.

## Validate
After generation, run validation:

```bash
cd ~/Projects/augur
python3 .github/scripts/validate_dashboard.py {name}
```
"""
            elif ide == "antigravity":
                content = f"""# Antigravity Workflow: {action}

```yaml
name: {action}-{name}
description: {action} for {name}

tasks:
  - name: execute-{action}
    type: code-generation
    prompt: |
      {f'Create an Augur skill named "{name}" with patterns: {", ".join(patterns) or "basic"}' if action == 'create_skill' else f'{action}: {json.dumps(action_params)}'}
```
"""
            else:  # copilot
                content = f"""# GitHub Copilot Instructions: {action}

## Use Copilot Chat
Open GitHub Copilot chat and use this prompt:

```
{f'Create an Augur skill named "{name}" with patterns: {", ".join(patterns) or "basic"}. Generate SKILL.md, Python scripts, dashboard components, and tests.' if action == 'create_skill' else f'{action}: {json.dumps(action_params)}'}
```
"""

            result = {
                "success": True,
                "content": content,
                "ide": ide,
                "action": action,
                "format": "yaml" if ide == "antigravity" else "markdown",
            }

            # Save to backlog if requested
            if save_to_backlog:
                try:
                    data_dir = get_project_root()
                    backlog_dir = data_dir / "factory" / "ide-backlog" / ide
                    backlog_dir.mkdir(parents=True, exist_ok=True)

                    filename = f"{action}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
                    file_path = backlog_dir / filename
                    file_path.write_text(content)
                    result["saved_to"] = str(file_path)
                except Exception as save_error:
                    logger.warning(f"Could not save to backlog: {save_error}")
                    result["save_error"] = str(save_error)

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"Failed to generate IDE instructions: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})
