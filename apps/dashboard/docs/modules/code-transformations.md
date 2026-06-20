# Code Transformations

The migration feature supports automated code transformations to bring existing skills into compliance with Augur conventions.

## Available Transformations

| Transformation | Description |
|----------------|-------------|
| Print to Logger | Convert `print()` statements to `logger.info()` |
| Logging Import | Replace `import logging` with `from src/lib.augur_logging` |
| Hardcoded Paths | Replace `/Users/xxx/...` paths with `get_project_root()` |

## Usage

Transformations can be applied via:
- **MCP tool**: `transform_code` with target skill path
- **API endpoint**: `POST /api/factory/transform`
- **Migration chain**: Automatically applied during `plugin-migration` chain

## Plugin Templates

Templates capture Augur conventions for common patterns:

| Template | Description | Creates |
|----------|-------------|---------|
| `skill-with-dashboard` | Skill with full dashboard UI | SKILL.md, dashboard.yaml, page.tsx, layout.tsx |
| `skill-with-mcp` | Skill with MCP tools | SKILL.md, mcp/__init__.py, mcp/tools.py |
| `skill-minimal` | Bare minimum skill | SKILL.md, version.yaml |

Each template includes Augur-specific conventions:
- `@augur` annotation blocks for tiering
- Safety configuration with iron law and circuit breaker
- Second brain alignment section
