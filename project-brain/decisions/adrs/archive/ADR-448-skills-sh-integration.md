---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related: []
tags: [skills-sh, marketplace, community, integration, cli]
---

# ADR-448: skills.sh Integration

## Context

Augur has no connection to the broader agent skills ecosystem. Users must manually discover community skills via browser, then figure out how to install them. skills.sh (by Vercel Labs) is the dominant open skills marketplace with 40+ supported clients and thousands of skills ranked by install count. Integrating it gives Augur users access to community skills through both CLI and dashboard.

## Decision

Create a new skill at `.claude/skills/skills.sh/` that wraps the `npx skills` CLI via `CLIBridge` to provide search, install, list, remove, and trending capabilities. The slash command is `/skills.sh` (avoiding collision with Claude Code's native `/skills`).

Key design points:
- **5 MCP tools**: `skills-sh-search`, `skills-sh-add`, `skills-sh-list`, `skills-sh-remove`, `skills-sh-trending`
- **CLIBridge**: wraps `npx` with `-y skills` prefix; 90s timeout for first-run package download
- **Install flow**: `npx skills add` installs to master client's native dir -> `skill_registry.py` auto-discovers at tier 2 -> `dev-sync` propagates -> optional `/import promote` for full Augur management
- **Dashboard surface**: data-table block on the import skill's page (not the skills.sh skill itself)
- **Multi-client**: single master client per install, `dev-sync` fans out; `--all` is forbidden
- **Client mapping**: reuses existing `_DIR_TO_MASTER` and `CLIENT_SKILL_DIRS` mappings

## Consequences

### Positive

- Access to thousands of community skills via both CLI and dashboard
- Leverages existing `npx skills` CLI (no custom download/validation code)
- Clean separation: skills.sh skill owns MCP tools, import skill owns dashboard surface

### Negative

- Dependency on external `npx skills` CLI and skills.sh service availability
- First-run `npx` package download adds latency (mitigated by 90s timeout)
- Community skills are instruction-only SKILL.md files -- no MCP tools, no dashboard pages

### Neutral

- Augur skill publishing to skills.sh is out of scope (future `/skills.sh publish`)
- Security review deferred to skills.sh platform vetting + user judgment

## Alternatives Considered

### Alternative 1: Direct API Integration

Call skills.sh REST API directly instead of wrapping CLI. Rejected because the CLI handles authentication, download, validation, and client-specific installation that would need reimplementation.

### Alternative 2: Custom Marketplace

Build Augur's own skill marketplace. Rejected as premature -- leverage the existing ecosystem first.

## References

- Design spec
