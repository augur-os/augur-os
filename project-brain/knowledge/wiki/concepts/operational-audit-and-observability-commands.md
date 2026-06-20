---
title: Operational Audit And Observability Commands
summary: Audit commands that inspect runtime health, policy boundaries, resource usage,
  logs, memory, and MCP wiring.
tags:
- operational-audit-and-observability-commands
- adaptive-loop-maintenance-surfaces
- daemon-maintenance-command-loops
- testing-and-quality-command-loops
- adaptive
- operational
- audit
- observability
aliases: []
related:
- '[[adaptive-loop-maintenance-surfaces]]'
- '[[daemon-maintenance-command-loops]]'
- '[[testing-and-quality-command-loops]]'
created: '2026-04-23T10:19:48Z'
_page_type: concept
_hub: adaptive
_sources:
- command:skills/loop-memory/commands/auto-context-audit.md
- command:skills/loop-memory/commands/auto-memory-leak.md
- command:skills/loop-observability/commands/auto-flow-optimizer.md
- command:skills/loop-observability/commands/auto-perf-profile.md
- command:skills/loop-observability/commands/auto-repo-sync.md
- command:skills/loop-ops/commands/auto-dependency-audit.md
- command:skills/loop-ops/commands/auto-fs-bypass.md
- command:skills/loop-ops/commands/auto-inspect.md
- command:skills/loop-ops/commands/auto-logs.md
- command:skills/loop-ops/commands/auto-mcp-health-audit.md
- command:skills/loop-ops/commands/auto-page-health.md
- command:skills/loop-ops/commands/auto-plugin-lint.md
_source_fingerprint: 08723a55bbcbee5e38cf28c2815b057d81a864e0bf0db5e7eaa6940c096e5054
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:17:12Z'
_cites:
- '[[command:skills/loop-memory/commands/auto-context-audit.md]]'
- '[[command:skills/loop-memory/commands/auto-memory-leak.md]]'
- '[[command:skills/loop-observability/commands/auto-flow-optimizer.md]]'
- '[[command:skills/loop-observability/commands/auto-perf-profile.md]]'
- '[[command:skills/loop-observability/commands/auto-repo-sync.md]]'
- '[[command:skills/loop-ops/commands/auto-dependency-audit.md]]'
- '[[command:skills/loop-ops/commands/auto-fs-bypass.md]]'
- '[[command:skills/loop-ops/commands/auto-inspect.md]]'
- '[[command:skills/loop-ops/commands/auto-logs.md]]'
- '[[command:skills/loop-ops/commands/auto-mcp-health-audit.md]]'
- '[[command:skills/loop-ops/commands/auto-page-health.md]]'
- '[[command:skills/loop-ops/commands/auto-plugin-lint.md]]'
_mentions:
- '[[concepts/adaptive-loop-maintenance-surfaces]]'
- '[[concepts/daemon-maintenance-command-loops]]'
- '[[concepts/testing-and-quality-command-loops]]'
_relates_to:
- '[[adaptive-loop-maintenance-surfaces]]'
- '[[adaptive]]'
- '[[audit]]'
- '[[daemon-maintenance-command-loops]]'
- '[[observability]]'
- '[[operational]]'
- '[[testing-and-quality-command-loops]]'
_entity_tier: 2
---

# Operational Audit And Observability Commands

## Compiled truth

### Current Thesis

Operational audit and observability commands exist to reveal hidden boundary failures before they show up as user-facing breakage. They measure and inspect the system layers that are easy to miss when you look only at page output or test status.

### What This Page Knows

This cluster brings together dependency audit, filesystem bypass checks, observability inspection, log hygiene, MCP health audits, page-health tool wiring checks, plugin structural lint, flow optimization, performance profiling, repo sync inspection, context-budget audits, and memory leak detection. The common pattern is instrumentation and policy verification. These commands do not just ask whether a feature works; they ask whether the runtime, the resource profile, and the wiring discipline are still coherent enough for the feature to keep working.

### Key Dimensions

- Inspection surfaces that explain where a failure lives before an agent starts editing code.
- Operational signals that complement, but do not replace, the explicit verification ladder in testing loops.
- Policy audits for MCP-first boundaries, page tool wiring, filesystem bypasses, and plugin structure.
- Runtime observability over health, logs, context budgets, memory use, and performance regressions.

### Recent Shifts

- MCP route and page-health auditing have become core observability work because broken wiring often looks like a UI defect from the user's perspective.
- Memory and context-budget audits make runtime resource pressure part of ordinary maintenance rather than a special emergency investigation.

### Open Tensions

- Audit surfaces can become noisy if they report every smell without ranking which ones threaten user-visible behavior first.
- Some commands can auto-fix safely, but deeper observability work still depends on human or agent judgment instead of blanket repair.

### How to Use This

Use this page when something feels operationally wrong but the failure boundary is not obvious yet. These commands help distinguish policy drift, runtime pressure, tool wiring defects, and resource leaks from ordinary test failures. After locating the boundary, hand off to [[concepts/testing-and-quality-command-loops]] for proof or to [[concepts/daemon-maintenance-command-loops]] when the issue belongs to long-running maintenance ownership.

### Open Questions

- How much of page-health and MCP-wiring diagnosis can be auto-repaired without violating the policy boundary these audits are meant to enforce?
- Which observability commands should eventually emit stronger prioritization so user-visible failures rise above lower-risk hygiene noise?

### Source Basis

- `command:skills/loop-memory/commands/auto-context-audit.md`: Measure MCP context token usage across agents and flag budget violations.
- `command:skills/loop-memory/commands/auto-memory-leak.md`: Detect dashboard memory leaks from polling, unbounded caches, and interval accumulation.
- `command:skills/loop-observability/commands/auto-flow-optimizer.md`: Analyze action dispatch configurations for mode mismatches.
- `command:skills/loop-observability/commands/auto-perf-profile.md`: Check response times, disk bloat, stale files, cache size, and flag IO/performance regressions.
- `command:skills/loop-observability/commands/auto-repo-sync.md`: Check repos for uncommitted or unpushed changes.
- `command:skills/loop-ops/commands/auto-dependency-audit.md`: Run dependency vulnerability scans against the dashboard package surface.
- `command:skills/loop-ops/commands/auto-fs-bypass.md`: Scan API routes for direct filesystem operations that should be routed through MCP tools.
- `command:skills/loop-ops/commands/auto-inspect.md`: Inspect operational dimensions like health, MCP, teams, logs, and context usage.
- `command:skills/loop-ops/commands/auto-logs.md`: Archive oversized runtime logs and keep log storage under control.
- `command:skills/loop-ops/commands/auto-mcp-health-audit.md`: Run the MCP health audit across route wiring, runtime probes, and safe fixes.
- `command:skills/loop-ops/commands/auto-page-health.md`: Validate MCP tool references used by dashboard pages.
- `command:skills/loop-ops/commands/auto-plugin-lint.md`: Process externally supplied plugin structural lint findings and apply narrow fixes.

### Related Concepts

- [[concepts/adaptive-loop-maintenance-surfaces]]
- [[concepts/daemon-maintenance-command-loops]]
- [[concepts/testing-and-quality-command-loops]]

## Timeline

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-memory/commands/auto-context-audit.md
  Measure MCP context token usage across agents and flag budget violations.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-memory/commands/auto-memory-leak.md
  Detect dashboard memory leaks from polling, unbounded caches, and interval accumulation.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-observability/commands/auto-flow-optimizer.md
  Analyze action dispatch configurations for mode mismatches.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-observability/commands/auto-perf-profile.md
  Check response times, disk bloat, stale files, cache size, and flag IO/performance regressions.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-observability/commands/auto-repo-sync.md
  Check repos for uncommitted or unpushed changes.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-ops/commands/auto-dependency-audit.md
  Run dependency vulnerability scans against the dashboard package surface.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-ops/commands/auto-fs-bypass.md
  Scan API routes for direct filesystem operations that should be routed through MCP tools.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-ops/commands/auto-inspect.md
  Inspect operational dimensions like health, MCP, teams, logs, and context usage.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-ops/commands/auto-logs.md
  Archive oversized runtime logs and keep log storage under control.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-ops/commands/auto-mcp-health-audit.md
  Run the MCP health audit across route wiring, runtime probes, and safe fixes.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-ops/commands/auto-page-health.md
  Validate MCP tool references used by dashboard pages.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-ops/commands/auto-plugin-lint.md
  Process externally supplied plugin structural lint findings and apply narrow fixes.
