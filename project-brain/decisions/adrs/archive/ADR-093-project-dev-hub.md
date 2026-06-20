---
status: Implemented
date: '2026-02-13'
deciders:
- User
- Claude
related: []
hub: null
tags:
- project
- dev
- hub
superseded_by: null
---

# ADR-093: Project Dev Hub

## Context

Augur's primary users are power users doing day-to-day software development. Currently, dev-related capabilities are scattered across:
- **crew/ bundle** (devops, developer, validator, frontend, advisor) — all dev-mode-only, contributing tabs to the `control` hub
- **observe/ service** — system health, logs, MCP status
- **action_buttons.yaml** — code_review, fix_bug, refactor_component, triage_backlog, execute_task
- **Slash commands** — /build, /nightly, /check, /review, /tidy, /coverage, /deploy, /fix, /debug, /chain, /swarm

There is no unified view of a software project's health: commits, CI/CD, codebase metrics, and development velocity are not tracked or visualized.

## Decision

Create a new **`project-dev`** plugin in `plugins/consulting/` that consolidates software development tracking into a single hub. Key design choices:

1. **Multi-project support** — registry of git repositories with Augur as the first seeded project
2. **YAML snapshots** — Python collectors gather data from git/gh CLI and store as YAML files in `data/snapshots/{project_id}/`
3. **Live + cached** — data is refreshed on demand via API routes that invoke Python collectors
4. **Dev workflow actions** — existing slash commands surfaced as action buttons in the hub
5. **Separate from crew/control** — crew hub stays for augur-internal devops; project-dev is for any project's metrics

## Consequences

### Positive

- Single dashboard for all development metrics across any project
- Multi-project tracking enables monitoring multiple codebases
- Dev workflow buttons centralized alongside metrics
- YAML snapshot pattern is consistent with other plugins (finance, career)

### Negative

- Data freshness depends on manual refresh or scheduled collection
- GitHub Actions data requires `gh` CLI authentication
- Some overlap with observe hub for system-level metrics

### Neutral

- crew/control hub remains unchanged for augur-internal tools
- Existing slash commands continue to work independently

## Alternatives Considered

### Alternative 1: Extend crew/control hub

Add metrics tabs to the existing control hub. Rejected because control is dev-mode-only and project-dev should work for any project, not just Augur internals.

### Alternative 2: External tool integration

Integrate with external project management tools (Jira, Linear). Rejected because it violates the local-first architecture (ADR-006) and adds external dependencies.

## References

- ADR-006: Local-first architecture
- ADR-087: Data folder elimination
- ADR-018: Plugin self-containment
