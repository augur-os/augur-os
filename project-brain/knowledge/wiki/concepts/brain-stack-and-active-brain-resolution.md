---
title: Brain Stack & Active-Brain Resolution
summary: Augur resolves an effective skill and instruction set from three ordered
  brain roots — Global, Personal, Project — with Project taking highest precedence.
  The active brain is declared in BRAIN.yaml and drives every session's context.
tags:
- brain-stack
- architecture
- skills
- projection
aliases:
- brain stack
- active brain resolution
- brain precedence
related:
- '[[agent-separation-mcp-skill-claude]]'
created: '2026-05-31T00:00:00Z'
_page_type: concept
_hub: dev
_sources:
- repo:project-brain/BRAIN.yaml
- adr:docs/adrs/ADR-794-standard-brain-workspace-files.md
- adr:docs/adrs/ADR-791-brain-scoped-standard-skill-source.md
_cites:
- '[[repo:project-brain/BRAIN.yaml]]'
- '[[adr:docs/adrs/ADR-794-standard-brain-workspace-files.md]]'
- '[[adr:docs/adrs/ADR-791-brain-scoped-standard-skill-source.md]]'
_compiler_version: concept-article-v4
_updated: '2026-05-31T00:00:00Z'
---

# Brain Stack & Active-Brain Resolution

## Compiled truth

Augur maintains a three-level brain stack — Global, Personal, and Project — resolved
in that priority order (Project > Personal > Global). Global is the Augur core: the
read-only platform baseline that owns projection engines, default policies, scanner
logic, and built-in adapters. Personal is the configured private vault. Project is
the brain attached to the current repository checkout, declared in `BRAIN.yaml` at
the brain root with fields: `schema_version`, `id`, `type`, `root`, `attached_project`,
and `description`. Each brain root hosts standard skill source under
`<brain-root>/capabilities/skills/<skill>/`, and Augur computes an effective skill
set with Project shadowing Personal shadowing Global. Shadow reporting must name the
roots that lost precedence so drift is always visible.

ADR-791 established that canonical brain-authored skill source is standard and generic
by default: no `x-augur-*` metadata, no Augur path imports, no dashboard page source.
Augur projects client-native exports (CLAUDE.md, AGENTS.md, Codex config) from the
effective skill set through `sync_agents`. ADR-794 aligned brain roots with common
agent-workspace files — `IDENTITY.md`, `SOUL.md`, `USER.md`, `AGENTS.md`, `MEMORY.md`,
`TOOLS.md`, `HEARTBEAT.md` — while keeping `BRAIN.yaml` as the canonical Augur
manifest. Standard root files are skeleton-created in project-brain/ and surfaced in
profile/manager snapshots, making the brain portable across AI clients without
re-authoring.

## Timeline

- 2026-05-29 — ADR-791 accepted: brain-scoped standard skill source as the default architecture.
- 2026-05-31 — ADR-794 implemented: standard brain workspace files aligned and projected.
- 2026-05-31 — Concept seeded from BRAIN.yaml, ADR-794, and ADR-791.
