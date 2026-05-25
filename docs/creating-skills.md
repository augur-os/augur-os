# Creating Skills

> **Skills are Harness layer 2** — modular expertise the AI client matches at runtime and forks into an isolated subagent. You author once in `project-brain/capabilities/skills/<skill-name>/SKILL.md`; the [Connection Layer](./architecture-mcp-gateway.md) projects the skill into every supported AI client's native format. See [architecture-overview.md](./architecture-overview.md#the-harness) for the full Harness model.

Skills are the building blocks of Augur OS. Each skill is a self-contained directory with instructions, tools, and optional dashboard pages.

## Skill Structure

```
project-brain/capabilities/skills/my-skill/
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
| `claude-code` | `project-brain/capabilities/skills/` |
| `cursor` | `.cursor/skills/` |
| `gemini` | `.gemini/skills/` |
| `codex` | `.codex/skills/` for project scope, `~/.codex/skills/` for global scope |

Codex skills are discovered from the client's own skill directories. Augur does not
use a separate Codex-native export flag, and it no longer mirrors prompt-style
workflow files into `.codex/prompts/`.

## Skill Ownership

Augur models skill lifecycle by ownership and canonical source, not by client install location:

- `global` — Augur-shipped skill in the core/project-brain capabilities tree
- `user` — private skill in the configured personal brain `capabilities/skills/`
- `team` — commercial shared/governed skill in a managed team brain
- `project` — repo-local skill in `<repo>/project-brain/capabilities/skills/`
- `external` — discovered outside managed canonical roots for awareness only

For managed skills, the canonical source is a brain-owned `capabilities/skills/` root: the repo's `project-brain/capabilities/skills/` tree for shipped/project capabilities, or the configured personal brain `capabilities/skills/` tree for user-owned private skills. Client-specific files such as `.codex/skills/`, `.codex/prompts/`, `.claude/skills/`, `.gemini/skills/`, and `.opencode/skills/` are export targets only. Which clients get exports is driven by the global enabled-client configuration, and Augur writes those exports repo-scoped by default.

## Vault-Backed Private Skills

Phase 1 splits private work into draft and active vault-owned surfaces:

- `project-brain/capabilities/skills/` — Augur-owned and repo-local project skills
- `get_vault_dir()/drafts/staging/` — private draft inventory; not canonical, not discovered, not exported, and not indexed
- configured personal brain `capabilities/skills/` — active private user skills; canonical, discovered, and exported through the same managed sync flow as repo skills

This replaces repo `staging/` as the long-term home for private skills. The repo no longer owns private draft inventory.

### When to use each location

- Put Augur-owned and repo-local project skills in `project-brain/capabilities/skills/<skill>/`
- Put unfinished private work in `get_vault_dir()/drafts/staging/<release>/skills/<skill>/`
- Put active private user skills in the configured personal brain `capabilities/skills/<skill>/`

### Promotion path

- `drafts/staging/...` -> configured personal brain `capabilities/skills/<skill>/` when a private skill becomes active
- configured personal brain `capabilities/skills/<skill>/` -> `project-brain/capabilities/skills/<skill>/` when the skill becomes Augur-owned product surface

Vault-backed private skills stay user-owned in metadata and UX:

- `ownership: user`
- `source_root: vault`
- `canonical: true`

Vault pages are reserved for a later phase. Phase 1 only activates vault-backed skills.

## Testing

Run your skill's tests:
```bash
pytest project-brain/capabilities/skills/my-skill/augur/tests/ -v
```

## Contributing a Skill

1. Create your skill directory
2. Test locally
3. Submit a PR to [augur-os/augur-os](https://github.com/augur-os/augur-os)
