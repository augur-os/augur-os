"""
MCP Server Generator Service

Generates MCP server files with domain-specific tools based on Five Pillar Framework.
"""

from pathlib import Path
from typing import Any, Optional, Dict


def generate_mcp_server(
    skill_dir: Path,
    skill_name: str,
    pillars: Dict[str, Any],
    rag_project_id: Optional[str] = None,
    domain: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """
    Generate MCP server file with domain-specific tools.

    Args:
        skill_dir: Skill directory path
        skill_name: Skill name (kebab-case)
        pillars: Five Pillar mapping with relevance scores
        rag_project_id: Optional RAG project ID
        domain: Optional domain name

    Returns:
        Tuple of (success, error_message)
    """
    # Determine relevant pillars
    relevant_pillars = [p for p, data in pillars.items() if data.get('relevance', 0) > 0.5]

    # Recall is always included
    if 'recall' not in relevant_pillars:
        relevant_pillars.append('recall')

    # Generate MCP server code
    mcp_code = generate_mcp_server_code(skill_name, relevant_pillars, rag_project_id, domain)

    # Write to file
    mcp_file = skill_dir / 'mcp.py'
    try:
        mcp_file.write_text(mcp_code, encoding='utf-8')
        mcp_file.chmod(0o755)  # Make executable
    except Exception as e:
        return False, f"Failed to write MCP server file: {e}"

    return True, None


def generate_mcp_server_code(
    skill_name: str, pillars: list[str], rag_project_id: Optional[str] = None, domain: Optional[str] = None
) -> str:
    """Generate MCP server Python code."""

    tool_name_prefix = skill_name.replace('-', '_')

    # Generate tool definitions
    tools = []
    tool_handlers = []

    # Recall tools (always included)
    if 'recall' in pillars:
        tools.append(f'''        Tool(
            name="{tool_name_prefix}_recall_search",
            description="Search {domain or skill_name} knowledge base using RAG",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "query": {{
                        "type": "string",
                        "description": "Search query"
                    }},
                    "k": {{
                        "type": "integer",
                        "description": "Number of results (default: 5)",
                        "default": 5
                    }}
                }},
                "required": ["query"]
            }}
        ),''')

        tool_handlers.append(f'''        if name == "{tool_name_prefix}_recall_search":
            query = arguments.get("query")
            k = arguments.get("k", 5)
            # TODO: Implement RAG search
            return [TextContent(type="text", text=f"Search results for: {{query}}")]''')

    # Capture tools
    if 'capture' in pillars:
        tools.append(f'''        Tool(
            name="{tool_name_prefix}_capture",
            description="Capture new {domain or skill_name} data",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "data": {{
                        "type": "string",
                        "description": "Data to capture"
                    }}
                }},
                "required": ["data"]
            }}
        ),''')

        tool_handlers.append(f'''        if name == "{tool_name_prefix}_capture":
            data = arguments.get("data")
            # TODO: Implement capture logic
            return [TextContent(type="text", text=f"Captured: {{data}}")]''')

    # Analyze tools
    if 'analyze' in pillars:
        tools.append(f'''        Tool(
            name="{tool_name_prefix}_analyze",
            description="Analyze {domain or skill_name} data and patterns",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "topic": {{
                        "type": "string",
                        "description": "Topic to analyze"
                    }}
                }},
                "required": ["topic"]
            }}
        ),''')

        tool_handlers.append(f'''        if name == "{tool_name_prefix}_analyze":
            topic = arguments.get("topic")
            # TODO: Implement analysis logic
            return [TextContent(type="text", text=f"Analysis for: {{topic}}")]''')

    # Execute tools
    if 'execute' in pillars:
        tools.append(f'''        Tool(
            name="{tool_name_prefix}_execute",
            description="Execute {domain or skill_name} action",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "action": {{
                        "type": "string",
                        "description": "Action to execute"
                    }}
                }},
                "required": ["action"]
            }}
        ),''')

        tool_handlers.append(f'''        if name == "{tool_name_prefix}_execute":
            action = arguments.get("action")
            # TODO: Implement execution logic
            return [TextContent(type="text", text=f"Executed: {{action}}")]''')

    # Grow tools
    if 'grow' in pillars:
        tools.append(f'''        Tool(
            name="{tool_name_prefix}_grow",
            description="Learn and grow {domain or skill_name} knowledge",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "data": {{
                        "type": "string",
                        "description": "New data to learn from"
                    }}
                }},
                "required": ["data"]
            }}
        ),''')

        tool_handlers.append(f'''        if name == "{tool_name_prefix}_grow":
            data = arguments.get("data")
            # TODO: Implement growth logic
            return [TextContent(type="text", text=f"Learned from: {{data}}")]''')

    tools_code = '\n'.join(tools)
    handlers_code = '\n'.join(tool_handlers)

    rag_config = ""
    if rag_project_id:
        rag_config = f'''
    # RAG Project Configuration
    RAG_PROJECT_ID = "{rag_project_id}"
'''

    return f'''#!/usr/bin/env python3
"""
MCP Server for {skill_name.replace('-', ' ').title()} skill.

Exposes domain-specific tools based on Five Pillar Framework.
"""

import json
from pathlib import Path
from typing import Any, Sequence

from mcp.server import Server
from mcp.types import (
    TextContent,
    Tool,
)
from src.logging import get_entity_logger

logger = get_entity_logger("mcp-{skill_name}")

# Initialize Server
server = Server("{skill_name}"){rag_config}

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
{tools_code}
    ]

@server.call_tool()
async def call_tool(
    name: str, arguments: Any
) -> Sequence[TextContent]:
    """Handle tool calls."""
    
    try:
{handlers_code}
        else:
            raise ValueError(f"Unknown tool: {{name}}")
    except Exception as e:
        logger.error(f"Error calling tool {{name}}: {{e}}")
        return [TextContent(type="text", text=f"Error: {{str(e)}}")]


if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    
    asyncio.run(main())
'''
