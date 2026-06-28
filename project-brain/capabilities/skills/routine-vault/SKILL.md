---
name: routine-vault
x-augur-type: autoloop
x-augur-group: augur_autoloops
x-augur-release: mvp
x-augur-license: MIT
description: Scheduled hygiene routines for vault and documentation upkeep — auditing CLAUDE.md and session context, linting frontmatter, repairing broken cross-references, pruning leaked memory, and archiving superseded file versions per folder.
x-augur-tab: vault
x-augur-tags:
- routine
- autoloop
- vault
- knowledge
- hygiene
- docs
- sweep
x-augur-dashboard-pages: []
x-augur-data-dir: routine-vault
x-augur-commands:
- id: auto-claude-md-audit
  type: workflow
  visibility: auto
  description: Validate instruction docs, hub lists, slash commands, and stale topic references.
  callable: scripts/claude_md_audit.py
  protocol: scan-fix
  loop:
    name: knowledge-enrichment
    tier: 2
    trigger: weekly
- id: auto-context-audit
  type: workflow
  visibility: auto
  description: Measure MCP context token usage across agents and flag budget violations.
  callable: scripts/context_audit.py
  protocol: scan-fix
  loop:
    name: observability
    tier: 1
    trigger: nightly
- id: auto-frontmatter-lint
  type: workflow
  visibility: auto
  description: Validate user-facing markdown/frontmatter structure per ADR-404.
  callable: scripts/frontmatter_lint.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 1
    trigger: nightly
- id: auto-markdowns
  type: workflow
  visibility: auto
  description: Scan and fix action prompt template quality across the repo.
  callable: scripts/markdown_ops.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 2
    trigger: nightly
- id: auto-memory-leak
  type: workflow
  visibility: auto
  description: Detect dashboard memory leaks from polling, unbounded caches, and interval accumulation.
  callable: scripts/memory_leak.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 2
    trigger: nightly
- id: auto-stale-refs
  type: workflow
  visibility: auto
  description: Detect and fix stale page and path references across actions and codebase.
  callable: scripts/stale_refs.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 1
    trigger: nightly
- id: auto-vault-hygiene
  type: workflow
  visibility: auto
  description: Monitor vault structure for data-separation violations and structural drift.
  callable: scripts/vault_hygiene_ops.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 1
    trigger: nightly
- id: auto-vault-structure-guard
  type: workflow
  visibility: auto
  description: Domains-layout structure guard — flags legacy top-level folders, unexpected root files, and test-artifact patterns in content areas (report-only).
  callable: scripts/structure_guard.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 1
    trigger: nightly
x-augur-config:
  contributions:
    commands:
    - id: auto-claude-md-audit
      type: workflow
      visibility: auto
      description: Validate instruction docs, hub lists, slash commands, and stale topic references.
      callable: scripts/claude_md_audit.py
      protocol: scan-fix
    - id: auto-context-audit
      type: workflow
      visibility: auto
      description: Measure MCP context token usage across agents and flag budget violations.
      callable: scripts/context_audit.py
      protocol: scan-fix
    - id: auto-frontmatter-lint
      type: workflow
      visibility: auto
      description: Validate user-facing markdown/frontmatter structure per ADR-404.
      callable: scripts/frontmatter_lint.py
      protocol: scan-fix
    - id: auto-markdowns
      type: workflow
      visibility: auto
      description: Scan and fix action prompt template quality across the repo.
      callable: scripts/markdown_ops.py
      protocol: scan-fix
    - id: auto-memory-leak
      type: workflow
      visibility: auto
      description: Detect dashboard memory leaks from polling, unbounded caches, and interval accumulation.
      callable: scripts/memory_leak.py
      protocol: scan-fix
    - id: auto-stale-refs
      type: workflow
      visibility: auto
      description: Detect and fix stale page and path references across actions and codebase.
      callable: scripts/stale_refs.py
      protocol: scan-fix
    - id: auto-vault-hygiene
      type: workflow
      visibility: auto
      description: Monitor vault structure for data-separation violations and structural drift.
      callable: scripts/vault_hygiene_ops.py
      protocol: scan-fix
    - id: auto-vault-structure-guard
      type: workflow
      visibility: auto
      description: Domains-layout structure guard — flags legacy top-level folders, unexpected root files, and test-artifact patterns in content areas (report-only).
      callable: scripts/structure_guard.py
      protocol: scan-fix
x-augur-loop:
  id: knowledge-enrichment
  skill: routine-vault
  automation:
    trigger: nightly
    runner: auto
    discover: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop_name: knowledge-enrichment
  isolation:
    mode: in-place
    surface: vault
  memory:
    trust: adaptive
---

# routine-vault

Vault and knowledge hygiene routines for memory curation, vault/doc structure, frontmatter, stale references, and stale artifact sweeping.

## Commands

- [commands/auto-claude-md-audit.md](commands/auto-claude-md-audit.md)
- [commands/auto-context-audit.md](commands/auto-context-audit.md)
- [commands/auto-frontmatter-lint.md](commands/auto-frontmatter-lint.md)
- [commands/auto-markdowns.md](commands/auto-markdowns.md)
- [commands/auto-memory-leak.md](commands/auto-memory-leak.md)
- [commands/auto-stale-refs.md](commands/auto-stale-refs.md)
- [commands/auto-vault-hygiene.md](commands/auto-vault-hygiene.md)
- [commands/auto-vault-structure-guard.md](commands/auto-vault-structure-guard.md)
- [commands/sweep.md](commands/sweep.md)
- [commands/sweep-stores.md](commands/sweep-stores.md)

## Scope

Use this routine skill for vault, memory, documentation hygiene, and stale artifact sweeping previously split across retired memory, hygiene, documentation, and repository loop skills.

## When to use

Use `routine-vault` to keep vault and documentation surfaces tidy — repairing stale references, linting frontmatter, and sweeping superseded artifacts — after large ingest sessions or on the nightly schedule.

## What it cleans

- **Memory** — leak-checks entries and curates durable memory.
- **Structure** — audits CLAUDE.md, session context, and document structure.
- **Frontmatter** — lints and repairs malformed YAML frontmatter.
- **References** — repairs links that point at moved or deleted paths.
- **Artifacts** — sweeps superseded versions into per-folder `.archive/` directories.

## How it runs

The hygiene workflows in `scripts/` run as nightly scan-fix processes; `/project sweep` runs interactively with user approval before any archive move.

## Examples

```bash
# Dry-run a stale-artifact sweep on a folder under Au-docs
/project sweep <folder>
```
