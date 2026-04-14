# Creating Skills

Skills are the building blocks of Augur OS. Each skill is a self-contained directory with instructions, tools, and optional dashboard pages.

## Skill Structure

```
skills/my-skill/
├── SKILL.md              # Skill definition (frontmatter + instructions)
├── augur/
│   └── dashboard/        # Optional Next.js dashboard pages
│       └── page.tsx
├── scripts/
│   └── mcp/              # Python MCP tool implementations
│       └── __init__.py
└── assets/
    └── seed-data/        # Optional template data
```

## SKILL.md Format

```markdown
---
name: my-skill
description: One-line description of what this skill does
x-augur-hub: dev
x-augur-master: claude-code
x-augur-type: domain
x-augur-mcp-tools:
  - my-tool
---

# My Skill

Instructions for AI agents in plain English. This is what gets executed.

## Commands

- `/my-command` — What it does

## Tools

- `my-tool` — Description of the MCP tool
```

## Adding MCP Tools

Declare tool metadata in `SKILL.md` frontmatter with `x-augur-*` fields. The
tool implementation itself lives in `scripts/mcp/`.

Create Python files in `scripts/mcp/`:

```python
# scripts/mcp/__init__.py
from mcp.server import Server

def register(mcp: Server):
    @mcp.tool(name="my-tool")
    async def my_tool(query: str) -> str:
        """Description of what this tool does."""
        return f"Result for {query}"
```

## Multi-Client Mastering

The `x-augur-master` frontmatter field determines which IDE client owns the skill:

| Value | Location |
|-------|----------|
| `claude-code` | `skills/` |
| `cursor` | `.cursor/skills/` |
| `gemini` | `.gemini/skills/` |
| `codex` | `.codex/skills/` for project scope, `~/.agents/skills/augur/` for global scope |

For Codex, Augur also mirrors prompt-style workflow files into `.codex/prompts/`, but
the workspace-native skill picker in Codex reads `.codex/skills/` for project-local
skills and `~/.agents/skills/` for global bundles.

To expose a managed skill in the Codex app-native picker, mark it explicitly:

```yaml
x-augur-codex-native: true
```

This export flag is separate from `x-augur-visibility`.

## Skill Ownership

Augur models skill lifecycle by ownership, not by install location:

- `augur` — canonical skill lives in `skills/` and is fully managed by Augur
- `external` — discovered outside `skills/` for awareness only; Augur does not rewrite it
- `adopted` — canonical skill lives in `skills/`, but keeps structured `upstream` metadata so you can track or rebase against the original source

For managed skills, `skills/` is the only source of truth. Client-specific files such as `.codex/skills/`, `.codex/prompts/`, `.claude/skills/`, `.gemini/skills/`, and `.opencode/skills/` are export targets only. Which clients get exports is driven by the global enabled-client configuration, and Augur writes those exports repo-scoped by default.

## Testing

Run your skill's tests:
```bash
pytest skills/my-skill/augur/tests/ -v
```

## Contributing a Skill

1. Create your skill directory
2. Test locally
3. Submit a PR to [augur-os/augur-os](https://github.com/augur-os/augur-os)
