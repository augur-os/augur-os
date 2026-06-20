---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related: [ADR-404, ADR-158]
hub: null
tags: [vault, data-cleanup, ideas, apple-sync]
superseded_by: null
---

# ADR-451: Ideas Vault Cleanup — Consolidate Scattered Idea Files

## Context

~70 startup/business/personal ideas were scattered across 5+ files in 3 different skills (growth, finance, lifestyle) with inconsistent formats (YAML, Notion checklists, markdown prose). Plan files for specific products (AI Chef, MoneyMind) were fragmented across 3 files each. No Apple Notes sync was configured. Finding or reviewing ideas required checking multiple locations.

## Decision

Consolidate all ideas into 3 canonical YAML+markdown files (one per owning skill), merge fragmented product plans into one file each, enable Apple Notes sync, and delete source files.

### Target structure

| File | Skill Owner | Ideas |
|------|------------|-------|
| `augur-career/venture-augur/ideas/ideas.md` | venture-augur | 70 startup/product ideas in 4 categories |
| `augur-life/finance/ideas/ideas.md` | finance | 13 investment/revenue ideas in 3 categories |
| `augur-life/lifestyle/ideas/ideas.md` | lifestyle | 34 personal/home/urban ideas in 3 categories |

### Plan merges

- AI Chef: 3 files -> `planning/ai-chef.md`
- MoneyMind/Firefly: 3 files -> `planning/moneymind.md`
- NextProject SDK: moved from `knowledge/startups/` to `planning/next-sdk.md`

### Cleanup rules

- Deduplicate, fix grammar/spelling, normalize format (`- **Name** — Description.`)
- YAML frontmatter + markdown (ADR-404)
- `sync_to_apple: true` for Apple Notes bidirectional sync
- Cross-reference links to plan files
- No editorial judgment on ideas — user reviews post-cleanup

## Consequences

### Positive

- Single source of truth per idea category
- Ideas are now Apple Notes-synced (browsable on phone)
- 11 scattered files replaced by 6 organized files
- Consistent format across all ideas

### Negative

- Ideas classification is subjective — some borderline items may need reclassification

### Neutral

- Existing detailed plan files for AI Chef, MoneyMind, NextProject SDK preserved in full (merged, not summarized)

## Alternatives Considered

### Alternative 1: Single master file

All ideas in one file. Rejected: breaks skill ownership boundaries (finance ideas shouldn't live in venture-augur).

### Alternative 2: One file per idea

Individual `.md` per idea (like job listings). Rejected: 70+ files is overkill for one-line ideas without plans.

## References

- Design spec: `docs/superpowers/specs/2026-03-19-ideas-vault-cleanup-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-19-ideas-vault-cleanup.md`
- ADR-404: Frontmatter format standard
- ADR-158: Apple Notes seamless editing integration

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated: []
  files_affected:
    - "~/Vault/Augur/augur-career/venture-augur/ideas/ideas.md"
    - "~/Vault/Augur/augur-life/finance/ideas/ideas.md"
    - "~/Vault/Augur/augur-life/lifestyle/ideas/ideas.md"
    - "~/Vault/Augur/augur-career/venture-augur/planning/ai-chef.md"
    - "~/Vault/Augur/augur-career/venture-augur/planning/moneymind.md"
    - "~/Vault/Augur/augur-career/venture-augur/planning/next-sdk.md"
  files_deleted:
    - "augur-career/growth/notes/notion-priority-dashboard-start-ups.md"
    - "augur-life/finance/notes/notion-priority-dashboard-businesses.md"
    - "augur-life/lifestyle/ideas/ideas.yaml"
    - "augur-career/venture-augur/planning/killer-dashboard-ideas.md"
    - "augur-career/venture-augur/planning/life-verticals-dashboard-ideas.md"
    - "augur-career/venture-augur/planning/ai-chef-plan.md"
    - "augur-career/venture-augur/planning/ai-chef-mealie-evaluation.md"
    - "augur-career/venture-augur/planning/ai-chef-implementation-plan.md"
    - "augur-career/venture-augur/planning/firefly-ai-dashboard-plan.md"
    - "augur-career/venture-augur/planning/firefly-dashboard-sprint-plan.md"
    - "augur-career/venture-augur/planning/firefly-ai-assistant-architecture.md"
```
