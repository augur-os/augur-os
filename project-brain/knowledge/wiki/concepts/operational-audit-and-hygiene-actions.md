---
title: Operational Audit And Hygiene Actions
summary: Action surfaces for observability inspection, policy audits, repo hygiene,
  and runtime health checks.
tags:
- operational-audit-and-hygiene-actions
- daemon-maintenance-command-loops
- documentation-and-repo-maintenance-commands
- operational-audit-and-observability-commands
- adaptive
- operational
- audit
- hygiene
aliases: []
related:
- '[[daemon-maintenance-command-loops]]'
- '[[documentation-and-repo-maintenance-commands]]'
- '[[operational-audit-and-observability-commands]]'
created: '2026-04-23T10:46:56Z'
_page_type: concept
_hub: adaptive
_sources:
- action:skills/loop-memory/augur/actions/auto-memory-leak-overview.md
- action:skills/loop-observability/augur/actions/auto-flow-optimizer-overview.md
- action:skills/loop-observability/augur/actions/auto-repo-sync-overview.md
- action:skills/loop-ops/augur/actions/auto-dependency-audit-overview.md
- action:skills/loop-ops/augur/actions/auto-fs-bypass-overview.md
- action:skills/loop-ops/augur/actions/auto-inspect-overview.md
- action:skills/loop-ops/augur/actions/auto-logs-overview.md
- action:skills/loop-repo/augur/actions/auto-git-health-overview.md
_source_fingerprint: 2a978699a95d29464efaa98092b97ea6b37fbe4c3cd667b4496b8d6d3b8bdb0d
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:17:12Z'
_cites:
- '[[action:skills/loop-memory/augur/actions/auto-memory-leak-overview.md]]'
- '[[action:skills/loop-observability/augur/actions/auto-flow-optimizer-overview.md]]'
- '[[action:skills/loop-observability/augur/actions/auto-repo-sync-overview.md]]'
- '[[action:skills/loop-ops/augur/actions/auto-dependency-audit-overview.md]]'
- '[[action:skills/loop-ops/augur/actions/auto-fs-bypass-overview.md]]'
- '[[action:skills/loop-ops/augur/actions/auto-inspect-overview.md]]'
- '[[action:skills/loop-ops/augur/actions/auto-logs-overview.md]]'
- '[[action:skills/loop-repo/augur/actions/auto-git-health-overview.md]]'
_mentions:
- '[[concepts/daemon-maintenance-command-loops]]'
- '[[concepts/documentation-and-repo-maintenance-commands]]'
- '[[concepts/operational-audit-and-observability-commands]]'
_relates_to:
- '[[adaptive]]'
- '[[audit]]'
- '[[daemon-maintenance-command-loops]]'
- '[[documentation-and-repo-maintenance-commands]]'
- '[[hygiene]]'
- '[[operational-audit-and-observability-commands]]'
- '[[operational]]'
_entity_tier: 3
---

# Operational Audit And Hygiene Actions

## Compiled truth

### Current Thesis

These actions expose Augur’s operational inspection layer in a user-visible form. They matter because many runtime or policy failures need fast orientation before anyone edits code, changes config, or runs a heavier maintenance command.

### What This Page Knows

The cluster brings together flow optimization, repo sync health, dependency audit, filesystem-bypass checks, observability inspection, log hygiene, memory leak detection, and git-health inspection. The durable pattern is audit before repair. These actions are how runtime and repo health become visible enough to prioritize whether the next step is a command run, a code fix, or an architectural boundary check.

### Key Dimensions

- A fast action layer that complements, but does not replace, the heavier observability and maintenance command families.
- Hygiene actions that highlight operational drift before it becomes user-visible failure.
- Observability entrypoints for logs, memory leaks, and broader runtime inspection.
- Policy-focused audit actions for filesystem bypasses, dependency risk, and repo sync health.

### Recent Shifts

- Operational diagnostics increasingly appear as stable actions, not only as internal loop outputs or engineer-only scripts.
- Runtime hygiene and policy audit concerns have become more central as the dashboard, MCP, and multi-client system surfaces have grown.

### Open Tensions

- Audit actions are only useful if they rank and frame findings well enough to guide the next step instead of dumping undifferentiated noise.
- The action layer can orient quickly, but deeper diagnosis still depends on the underlying command and architecture surfaces staying clear.

### How to Use This

Use this page when something feels wrong operationally and you need a fast diagnostic surface: inspect repo sync, logs, memory, dependencies, bypass violations, or general observability state. These actions help decide where to dig next without overcommitting to one repair path too early.

### Open Questions

- How much of the observability and hygiene stack should remain action-accessible versus daemon-driven or command-only?
- Which audit actions should grow stronger prioritization so the most user-visible risks rise above general hygiene noise?

### Source Basis

- `action:skills/loop-memory/augur/actions/auto-memory-leak-overview.md`: View Detect dashboard memory leaks from polling, unbounded caches, and interval accumulation.
- `action:skills/loop-observability/augur/actions/auto-flow-optimizer-overview.md`: View Detect dispatch mode mismatches across actions for adaptive engine and self-healing automation.
- `action:skills/loop-observability/augur/actions/auto-repo-sync-overview.md`: View Check repos for uncommitted/unpushed changes, sync at higher difficulty for adaptive engine and self-healing automation.
- `action:skills/loop-ops/augur/actions/auto-dependency-audit-overview.md`: Review dependency audit status and repair policy from the consolidated loop-ops surface.
- `action:skills/loop-ops/augur/actions/auto-fs-bypass-overview.md`: View the absorbed filesystem-bypass audit from the consolidated loop-ops surface.
- `action:skills/loop-ops/augur/actions/auto-inspect-overview.md`: Inspect observability dimensions and context usage from the consolidated loop-ops surface.
- `action:skills/loop-ops/augur/actions/auto-logs-overview.md`: Review log archive status and runtime log hygiene from the consolidated loop-ops surface.
- `action:skills/loop-repo/augur/actions/auto-git-health-overview.md`: Review repository footprint and git maintenance from the consolidated loop-repo surface.

### Related Concepts

- [[concepts/daemon-maintenance-command-loops]]
- [[concepts/documentation-and-repo-maintenance-commands]]
- [[concepts/operational-audit-and-observability-commands]]

## Timeline

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-memory/augur/actions/auto-memory-leak-overview.md
  View Detect dashboard memory leaks from polling, unbounded caches, and interval accumulation.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-observability/augur/actions/auto-flow-optimizer-overview.md
  View Detect dispatch mode mismatches across actions for adaptive engine and self-healing automation.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-observability/augur/actions/auto-repo-sync-overview.md
  View Check repos for uncommitted/unpushed changes, sync at higher difficulty for adaptive engine and self-healing automation.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-ops/augur/actions/auto-dependency-audit-overview.md
  Review dependency audit status and repair policy from the consolidated loop-ops surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-ops/augur/actions/auto-fs-bypass-overview.md
  View the absorbed filesystem-bypass audit from the consolidated loop-ops surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-ops/augur/actions/auto-inspect-overview.md
  Inspect observability dimensions and context usage from the consolidated loop-ops surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-ops/augur/actions/auto-logs-overview.md
  Review log archive status and runtime log hygiene from the consolidated loop-ops surface.

- _at: 2026-05-03T13:17:12Z  _source: action:skills/loop-repo/augur/actions/auto-git-health-overview.md
  Review repository footprint and git maintenance from the consolidated loop-repo surface.
