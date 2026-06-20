---
status: Implemented
date: 2026-05-21
deciders:
  - gsannikov
related: [ADR-754, ADR-768, ADR-769]
hub: brain
tags: [brain, project-brain, migration, shared-vault]
superseded_by: null
spec_file: 2026-05-21-project-brain-physical-migration-design.md
plan_file: 2026-05-21-project-brain-physical-migration.md
---

# ADR-770: Project-Brain Physical Migration

> **ADR-770 is an index file.** The substantive design and implementation steps
> live in the linked spec + plan. This file carries pointers, status, and a
> one-line decision summary.

## Decision summary

Move durable Augur project-brain content from legacy `shared-vault/` into the
canonical `project-brain/` layout and update path/discovery surfaces
exhaustively.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-21-project-brain-physical-migration-design.md`](../superpowers/specs/2026-05-21-project-brain-physical-migration-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-21-project-brain-physical-migration.md`](../superpowers/plans/2026-05-21-project-brain-physical-migration.md)

## Status notes

Implemented 2026-05-21. Durable project-brain content now lives under
`project-brain/`, canonical skill discovery resolves
`project-brain/capabilities/skills`, mapped repository sources are declared in
`project-brain/config/mapped-sources.yaml`, and the remaining `shared-vault/`
tree is a compatibility pointer. Focused Python, dashboard Jest, real-data
indexing, MCP browse-index, and browser checks passed against the migrated
worktree.

## Related

- ADR-769: Foundation and `augur init`.
- ADR-771: AI-client projection migration after physical paths are stable.

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - "shared-vault/skills -> project-brain/capabilities/skills"
    - "shared-vault/wiki -> project-brain/knowledge/wiki"
    - "shared-vault/notes -> project-brain/knowledge/notes"
    - "shared-vault/sources -> project-brain/knowledge/sources"
    - "shared-vault/inbox -> project-brain/inbox"
    - "shared-vault/archive -> project-brain/archive"
    - "shared-vault/config -> project-brain/config"
    - "shared-vault/drafts -> project-brain/drafts"
  apis_changed:
    - "src/config/paths.py: project-brain helpers become canonical for project content"
    - "project-brain manifest/config: mapped durable repo-doc sources are explicit"
  patterns_deprecated:
    - "shared-vault as canonical Augur project-brain root"
  files_affected:
    - "src/config/paths.py"
    - "src/plugins/skill_discovery.py"
    - "docs/adrs, docs/superpowers, docs/agent-topics mapped into project-brain"
    - "shared-vault/skills/ai/scripts/sync_agents/*"
    - "apps/dashboard discovery and Browse transforms"
    - "tests covering skill, command, MCP, and dashboard discovery"
```

## Implementation Prompt

To execute this ADR, run:

```text
/adr implement ADR-770
```
