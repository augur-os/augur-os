---
title: Documentation And Repo Maintenance Commands
summary: Commands that keep docs, frontmatter, references, hub coverage, and repository
  structure aligned with the live system.
tags:
- documentation-and-repo-maintenance-commands
- adaptive-loop-maintenance-surfaces
- platform-admin-and-skill-quality-commands
- adaptive
- documentation
- repo
- maintenance
- commands
aliases: []
related:
- '[[adaptive-loop-maintenance-surfaces]]'
- '[[platform-admin-and-skill-quality-commands]]'
created: '2026-04-23T10:19:48Z'
_page_type: concept
_hub: adaptive
_sources:
- command:skills/loop-docs/commands/auto-claude-md-audit.md
- command:skills/loop-docs/commands/auto-command-help-coverage.md
- command:skills/loop-docs/commands/auto-frontmatter-lint.md
- command:skills/loop-docs/commands/auto-markdowns.md
- command:skills/loop-docs/commands/auto-skill-usage.md
- command:skills/loop-docs/commands/auto-stale-refs.md
- command:skills/loop-hub-coverage/commands/auto-adaptive-hub-coverage.md
- command:skills/loop-hub-coverage/commands/auto-brain-hub-coverage.md
- command:skills/loop-hub-coverage/commands/auto-command-hub-coverage.md
- command:skills/loop-hub-coverage/commands/auto-life-hub-coverage.md
- command:skills/loop-hub-coverage/commands/auto-studio-hub-coverage.md
- command:skills/loop-repo/commands/auto-dir-alignment.md
- command:skills/loop-repo/commands/auto-file-growth.md
- command:skills/loop-repo/commands/auto-git-health.md
- command:skills/loop-repo/commands/auto-vault-hygiene.md
_source_fingerprint: 3bef6b8c02a86c1901af7974475b975b06ea7a61963c81beb2ed48533fe8507b
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:17:12Z'
_cites:
- '[[command:skills/loop-docs/commands/auto-claude-md-audit.md]]'
- '[[command:skills/loop-docs/commands/auto-command-help-coverage.md]]'
- '[[command:skills/loop-docs/commands/auto-frontmatter-lint.md]]'
- '[[command:skills/loop-docs/commands/auto-markdowns.md]]'
- '[[command:skills/loop-docs/commands/auto-skill-usage.md]]'
- '[[command:skills/loop-docs/commands/auto-stale-refs.md]]'
- '[[command:skills/loop-hub-coverage/commands/auto-adaptive-hub-coverage.md]]'
- '[[command:skills/loop-hub-coverage/commands/auto-brain-hub-coverage.md]]'
- '[[command:skills/loop-hub-coverage/commands/auto-command-hub-coverage.md]]'
- '[[command:skills/loop-hub-coverage/commands/auto-life-hub-coverage.md]]'
- '[[command:skills/loop-hub-coverage/commands/auto-studio-hub-coverage.md]]'
- '[[command:skills/loop-repo/commands/auto-dir-alignment.md]]'
- '[[command:skills/loop-repo/commands/auto-file-growth.md]]'
- '[[command:skills/loop-repo/commands/auto-git-health.md]]'
- '[[command:skills/loop-repo/commands/auto-vault-hygiene.md]]'
_mentions:
- '[[concepts/adaptive-loop-maintenance-surfaces]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
_relates_to:
- '[[adaptive-loop-maintenance-surfaces]]'
- '[[adaptive]]'
- '[[commands]]'
- '[[documentation]]'
- '[[maintenance]]'
- '[[platform-admin-and-skill-quality-commands]]'
- '[[repo]]'
_entity_tier: 2
---

# Documentation And Repo Maintenance Commands

## Compiled truth

### Current Thesis

Documentation and repo maintenance commands protect Augur from a specific failure mode: the system evolves, but the instructions, paths, hub references, and repository shape stop matching reality. This cluster exists to keep those surfaces synchronized.

### What This Page Knows

The commands here span instruction audits, command-help coverage, frontmatter validation, markdown prompt coverage, stale reference repair, hub-specific path repair, directory alignment, runaway file growth, git object growth, and vault hygiene. Taken together, they form the repo-structure maintenance layer. Their real job is not polishing prose; it is preserving trustworthy documentation, stable paths, and manageable repository layout as the system keeps migrating and generating new surfaces.

### Key Dimensions

- Instruction and help-surface audits so command and skill docs still reflect live behavior.
- Markdown and frontmatter validation that keeps user-facing files parseable and portable.
- Reference and path repair after migrations, especially across hubs and moved skill layouts.
- Repository and vault hygiene checks for structural drift, file growth, and misplaced content.

### Recent Shifts

- Hub coverage repair has become a distinct maintenance pattern because path migrations now affect multiple generated and hand-written surfaces at once.
- Repository hygiene commands increasingly guard against silent drift in generated docs, vault layout, and object growth rather than only catching obvious markdown mistakes.

### Open Tensions

- A broad documentation repair pass can accidentally collapse meaningful differences between hubs if it is treated as generic text cleanup.
- Repo hygiene checks need to stay conservative so they surface drift without turning into destructive cleanup automation.

### How to Use This

Use this family when the system changed and you need to restore trust in paths, instructions, help coverage, or structural layout. These commands are especially relevant after migrations, generator changes, hub refactors, and cleanup work that may leave stale references behind. Pair them with [[concepts/platform-admin-and-skill-quality-commands]] when the maintenance work also needs verification or merge coordination.

### Open Questions

- Where should repo hygiene stop reporting drift and start applying safe structural fixes automatically?
- Which documentation surfaces are durable enough to maintain here versus regenerate from skill-owned metadata each time?

### Source Basis

- `command:skills/loop-docs/commands/auto-claude-md-audit.md`: Validate instruction docs against actual project state.
- `command:skills/loop-docs/commands/auto-command-help-coverage.md`: Audit command-hub `SKILL.
- `command:skills/loop-docs/commands/auto-frontmatter-lint.md`: Validate user-facing markdown/frontmatter structure per ADR-404.
- `command:skills/loop-docs/commands/auto-markdowns.md`: Scan and fix prompt-template coverage for dashboard actions.
- `command:skills/loop-docs/commands/auto-skill-usage.md`: Analyze skill invocation logs to identify underused and heavily used skills.
- `command:skills/loop-docs/commands/auto-stale-refs.md`: Detect and fix stale page and path references across actions and code.
- `command:skills/loop-hub-coverage/commands/auto-adaptive-hub-coverage.md`: Repair stale adaptive-hub references after client-native migration.
- `command:skills/loop-hub-coverage/commands/auto-brain-hub-coverage.md`: Repair stale brain-hub references across skill docs and RAG-related paths.
- `command:skills/loop-hub-coverage/commands/auto-command-hub-coverage.md`: Repair stale command-hub references after skill and daemon path migrations.
- `command:skills/loop-hub-coverage/commands/auto-life-hub-coverage.md`: Repair stale life-hub references tied to moved data dirs and channel paths.
- `command:skills/loop-hub-coverage/commands/auto-studio-hub-coverage.md`: Repair stale studio-hub references after the move to the live `skills/` layout.
- `command:skills/loop-repo/commands/auto-dir-alignment.md`: Validate first-level directories in managed locations against live skill names and `.

### Related Concepts

- [[concepts/adaptive-loop-maintenance-surfaces]]
- [[concepts/platform-admin-and-skill-quality-commands]]

## Timeline

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-docs/commands/auto-claude-md-audit.md
  Validate instruction docs against actual project state.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-docs/commands/auto-command-help-coverage.md
  Audit command-hub `SKILL.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-docs/commands/auto-frontmatter-lint.md
  Validate user-facing markdown/frontmatter structure per ADR-404.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-docs/commands/auto-markdowns.md
  Scan and fix prompt-template coverage for dashboard actions.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-docs/commands/auto-skill-usage.md
  Analyze skill invocation logs to identify underused and heavily used skills.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-docs/commands/auto-stale-refs.md
  Detect and fix stale page and path references across actions and code.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-hub-coverage/commands/auto-adaptive-hub-coverage.md
  Repair stale adaptive-hub references after client-native migration.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-hub-coverage/commands/auto-brain-hub-coverage.md
  Repair stale brain-hub references across skill docs and RAG-related paths.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-hub-coverage/commands/auto-command-hub-coverage.md
  Repair stale command-hub references after skill and daemon path migrations.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-hub-coverage/commands/auto-life-hub-coverage.md
  Repair stale life-hub references tied to moved data dirs and channel paths.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-hub-coverage/commands/auto-studio-hub-coverage.md
  Repair stale studio-hub references after the move to the live `skills/` layout.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-repo/commands/auto-dir-alignment.md
  Validate first-level directories in managed locations against live skill names and `.
