---
status: Implemented
date: 2026-03-18
deciders:
  - Gur Sannikov
related: []
hub: system
tags:
  - google-workspace
  - cli
  - migration
  - gws
superseded_by: null
---

# ADR-439: Google Workspace gws CLI Migration [RECONSTRUCTED]

## Context

The Google Workspace integration in Augur previously used `gog`, an unofficial community CLI for Google APIs. While functional, `gog` had limited maintenance, inconsistent API coverage, and no official backing from Google. Google released the official `gws` CLI (`@googleworkspace/cli` on npm) providing first-party support for Gmail, Calendar, Drive, Docs, Sheets, Tasks, Chat, and Contacts with built-in OAuth handling via `gws auth login`.

## Decision

Migrate the Google Workspace skill from the `gog` CLI to the official `gws` CLI (`npm install -g @googleworkspace/cli`). This affects:

### CLI Integration

- Install command: `npm install -g @googleworkspace/cli`
- Auth flow: `gws auth login` (opens browser, handles callback automatically)
- Auth status: `gws auth status`
- Version check: `gws --version`

### SKILL.md Frontmatter

The `google-workspace` skill's `x-augur-cli-integrations` frontmatter was updated to reference `gws`:

```yaml
x-augur-cli-integrations:
  - name: gws
    install: "npm install -g @googleworkspace/cli"
    version_cmd: "gws --version"
    requires_config: true
    config_check: "gws auth status"
    homepage: "https://github.com/googleworkspace/cli"
```

### MCP Tool Wrappers

All Python MCP tool wrappers in the google-workspace skill were updated to call `gws` subcommands instead of `gog`. The tool names and API surface remained unchanged -- this was a backend implementation swap, transparent to MCP consumers.

### Service Coverage

The `gws` CLI provides coverage for: Gmail (list, read, search, send, trash, archive), Calendar (list, get, create, update, delete), Drive (list, search, info, download), Docs (list, read, create), Sheets (read, append, create), Tasks (list, create, complete), Chat (send), and Contacts (search).

## Consequences

### Positive

- Official Google-backed CLI with guaranteed API compatibility and updates
- Single-step OAuth flow (`gws auth login`) replaces multi-step credential setup
- AES-256-GCM encrypted credential storage by `gws` itself
- Broader API coverage (Tasks, Chat, Contacts) out of the box

### Negative

- Users with existing `gog` installations must install `gws` and re-authenticate
- Breaking change for any external tools that depended on `gog` CLI being present

### Neutral

- MCP tool names (`google-gmail-list`, `google-calendar-create`, etc.) are unchanged
- Dashboard API routes and UI components are unaffected
- The migration is a backend CLI swap, invisible to dashboard and MCP consumers

## Alternatives Considered

### Alternative 1: Keep gog and Add gws as Fallback

Support both CLIs with runtime detection.

**Rejected because**: Maintaining two CLI wrappers doubles the code surface and testing burden. The official CLI is strictly superior -- a clean cutover is simpler and more reliable.

### Alternative 2: Direct Google API Calls (No CLI)

Call Google APIs directly from Python using `google-api-python-client`.

**Rejected because**: Requires managing OAuth tokens, refresh logic, and API pagination in Augur code. The `gws` CLI handles all of this, keeping the MCP tool wrappers thin.

## References

- Commit: `feat: migrate Google Workspace CLI from gog to official gws (ADR-439)`
- Google Workspace skill: `.claude/skills/google-workspace/SKILL.md`
- gws CLI: `https://github.com/googleworkspace/cli`
