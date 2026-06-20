---
status: Implemented
date: 2026-03-22
deciders:
  - Gur Sannikov
related: []
hub: command
tags:
  - skills-sh
  - community-skills
  - mcp-tool
  - cli-bridge
superseded_by: null
---

# ADR-472: Skills.sh Integration

## Context

Skills.sh (by Vercel Labs) is an open agent skills ecosystem supporting 40+ agent clients. Augur currently has no way to discover, install, or manage community skills from this marketplace, limiting the skill ecosystem to manually authored skills.

## Decision

Create a new `.claude/skills/skills.sh/` skill that wraps the `npx skills` CLI via CLIBridge, exposing 5 MCP tools:

- `skills-sh-search`: Search skills.sh for community skills matching a query
- `skills-sh-add`: Install a skill to a specified master client (claude-code, codex, gemini, cursor)
- `skills-sh-list`: List skills installed via skills.sh
- `skills-sh-remove`: Uninstall a skills.sh-installed skill
- `skills-sh-trending`: Show top-20 trending skills from the leaderboard

The import skill gets a `skills-sh-catalog` dashboard block (data-table with search) and an `install-community-skill` action. The external MCP registry gets a `skills-sh` CLI entry. Post-install flow: `npx skills add` installs to master client, Augur auto-discovers it, `dev-sync` propagates to other clients.

## Consequences

### Positive
- Access to community skill ecosystem without leaving Augur
- Cross-client skill installation via a single interface
- Dashboard visibility of installed community skills

### Negative
- Depends on Node.js being available for `npx`
- First-run `npx -y skills` download adds 90s latency
- Community skill quality is not controlled by Augur

### Neutral
- Client mapping: claude-code -> claude, codex -> codex, gemini -> gemini-cli, cursor -> cursor
- 90s default timeout accounts for first-run package download

## Alternatives Considered

### Alternative 1: Direct GitHub API integration
Fetch skill repos directly from GitHub instead of using the skills.sh CLI. Rejected because it bypasses the skills.sh ecosystem's discovery, install format, and client targeting features.

## References
- Plan: `docs/superpowers/plans/2026-03-19-skills-sh-integration.md`
- Spec: `docs/superpowers/specs/2026-03-19-skills-sh-integration-design.md`
