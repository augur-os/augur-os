# Augur MCP Server

Expose AI skills through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) for use with Claude, ChatGPT, Cursor, and any MCP-compatible client.

## Features

- **Skill Discovery**: Automatically discovers skills from your configured skill roots
- **Token Optimization**: Lazy loading of skills and modules with caching
- **Self-Update Loop**: Modules can evolve during conversations
- **Smart Matching**: Find skills by natural language query
- **Multi-Platform**: Works with any MCP-compatible client
- **Pattern Learning**: Capture improvements and apply them later
- **Backups & Rollback**: Every change creates a backup

## Installation

```bash
pip install augur-mcp
```

## Quick Start

### 1. Configure Environment

```bash
export AUGUR_ROOT=/path/to/your/data
```

### 2. Run the Server

```bash
# stdio transport (for Claude Desktop, Cursor)
augur-mcp

# SSE transport (for web clients)
augur-mcp --transport sse --host 0.0.0.0 --port 8000

# HTTP transport with OAuth
augur-mcp --transport streamable-http --auth oauth
```

### 3. Configure Your Client

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "augur": {
      "command": "augur-mcp",
      "env": {
        "AUGUR_ROOT": "/path/to/data"
      }
    }
  }
}
```

**Cursor** (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "augur": {
      "command": "augur-mcp",
      "env": {
        "AUGUR_ROOT": "/path/to/data"
      }
    }
  }
}
```

## Configuration

All configuration is done via environment variables:

| Variable          | Description                     | Default |
| ----------------- | ------------------------------- | ------- |
| `AUGUR_ROOT`      | Project root (for monorepo dev) | None    |
| `AUGUR_CORE`      | Legacy alias for project root   | None    |
| `AUGUR_LOG_LEVEL` | Logging level                   | `INFO`  |
| `AUGUR_METRICS`   | Enable usage metrics            | `true`  |
| `AUGUR_CACHE`     | Enable skill caching            | `true`  |
| `AUGUR_CACHE_TTL` | Cache TTL in seconds            | `300`   |

## Skill Structure

In the monorepo, the canonical project/team source of truth is
`project-brain/capabilities/skills/`. Client-specific exports such as `.claude/skills/` and
`.codex/prompts/` are generated outputs, not editable source.

```
project-brain/capabilities/skills/
└── my-skill/
    ├── SKILL.md
    ├── commands/
    ├── references/
    ├── scripts/
    ├── modules/
    ├── assets/
    └── augur/
```

Agent definitions are sourced from `plugins/agents/` and synced into client
runtime folders as generated copies.

### SKILL.md Format

```markdown
---
name: my-skill
version: 1.0.0
description: What this skill does
triggers:
  - "keyword one"
  - "keyword two"
---

# My Skill

## Capabilities

- Capability one
- Capability two

## Commands

- `/command`: Description
```

## MCP Tools

The server exposes these core tools:

| Tool             | Description                           |
| ---------------- | ------------------------------------- |
| `list-skills`    | List all available skills             |
| `get-skill`      | Get skill details and overview        |
| `load-module`    | Load a specific knowledge module      |
| `load-reference` | Load reference documentation          |
| `find-skill`     | Find skills by natural language query |
| `skill-action`   | Execute a skill action or command     |
| `agent-registry` | List registered agents and sync state |

Plus dynamic tools registered by each skill's scripts.

## Development

### Running from Source

```bash
git clone https://github.com/augur/augur-mcp
cd augur-mcp
pip install -e ".[dev]"
augur-mcp
```

### Running Tests

```bash
pytest
```

### Type Checking

```bash
mypy augur_core augur_framework augur_shared
```

## Custom Skill Registry

You can implement a custom skill registry by subclassing `SkillRegistry`:

```python
from augur_shared.interfaces import SkillRecord, SkillRegistry

class MyRegistry(SkillRegistry):
    def list_skills(self, *, include_disabled: bool = False) -> list[SkillRecord]:
        # Your implementation
        ...

    def resolve_skill(self, name: str, *, include_disabled: bool = False) -> SkillRecord | None:
        # Your implementation
        ...

    def get_plugins_dir(self) -> Path:
        return Path("/my/skills")
```

Then configure via entry point in your `pyproject.toml`:

```toml
[project.entry-points."augur_mcp.registry"]
my-registry = "my_package:MyRegistry"
```

## License

MIT License

## Links

- [Documentation](https://docs.augur.ai)
- [GitHub](https://github.com/augur/augur-mcp)
- [MCP Specification](https://modelcontextprotocol.io)
