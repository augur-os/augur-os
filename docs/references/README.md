# Reference Documents

Surfaced reference docs from the plugin tree for agent discoverability.

## Why
Reference docs buried deep in `apps/dashboard/docs/references/` are hard for agents to find. This directory provides a discoverable surface.

## Canonical Sources
Files here are copies. Canonical sources live in the skill:
- `design-standards.md` <- `apps/dashboard/docs/references/design-standards.md`
- `agents-page-design-pattern.md` <- `apps/dashboard/docs/references/agents-page-design-pattern.md`

## Local Reference Docs

These are maintained directly in this directory:

- `agent-vs-mcp-checklist.md` — where orchestration belongs: agent vs MCP vs docs vs scheduler
- `agent-vs-mcp-examples.md` — concrete good-vs-bad Augur implementations for the architecture pattern
- `file-placement-matrix.md` — where new files, skills, reports, and wiki inputs belong

## Sync
Copies are refreshed during nightly sync. To manually sync:
```bash
cp apps/dashboard/docs/references/*.md docs/references/
```
