# Augur Subagent Definitions

This directory is the **canonical source** for Augur subagent definitions.

## Convention

Agent definitions live in `plugins/agents/` — a platform-neutral location since agents are synced to all IDE clients (Claude Code, Gemini, Codex, Cursor, Copilot, etc.), not just one.

Each agent is an `.md` file with YAML frontmatter:

```
---
name: <agent-name>
description: '<short description>'
mode: plan | act
model: haiku | sonnet | opus
mcpServers:
  - augur
x-augur-master: claude-code
---

# <Agent Title>
...
```

`registry.json` contains the structured agent registry with tier configs, tool lists, safety constraints, and escalation paths.

## Sync to .claude/agents/

The stub generator (`scripts/generate_client_stubs.py`) syncs these files to `.claude/agents/` automatically. Each synced file is prepended with `<!-- AUGUR-GENERATED -->` so the generator knows which files it owns.

Rules:
- Files in `.claude/agents/` **with** the `<!-- AUGUR-GENERATED -->` marker are overwritten on each sync.
- Files in `.claude/agents/` **without** the marker are user-created agents and are never touched.
- If a source file is removed from `plugins/agents/`, the corresponding generated stub in `.claude/agents/` is deleted on the next sync.

## Editing Agents

Always edit files in `plugins/agents/` (this directory), never directly in `.claude/agents/`. Run `scripts/generate_client_stubs.py` (or `/dev-build`) to propagate changes.

## References

- [Claude Code Subagents documentation](https://docs.anthropic.com/en/docs/claude-code/sub-agents)
- `.claude-plugin/plugin.json` — plugin manifest
- `scripts/generate_client_stubs.py` — stub generator
