---
title: Testing And Quality Command Loops
summary: Verification commands that move from formatting and lint through build, API,
  MCP, route, and end-to-end checks.
tags:
- testing-and-quality-command-loops
- operational-audit-and-observability-commands
- platform-admin-and-skill-quality-commands
- adaptive
- testing
- quality
- command
- loops
aliases: []
related:
- '[[operational-audit-and-observability-commands]]'
- '[[platform-admin-and-skill-quality-commands]]'
created: '2026-04-23T10:19:48Z'
_page_type: concept
_hub: adaptive
_sources:
- command:skills/loop-quality/commands/auto-format.md
- command:skills/loop-quality/commands/auto-lint.md
- command:skills/loop-quality/commands/auto-ui-quality.md
- command:skills/loop-quality/commands/auto-yaml-lint.md
- command:skills/loop-test/commands/auto-e2e-actions.md
- command:skills/loop-test/commands/auto-e2e-pipeline.md
- command:skills/loop-test/commands/auto-test-api.md
- command:skills/loop-test/commands/auto-test-build.md
- command:skills/loop-test/commands/auto-test-dashboard.md
- command:skills/loop-test/commands/auto-test-links.md
- command:skills/loop-test/commands/auto-test-mcp-commands.md
- command:skills/loop-test/commands/auto-test-mcp.md
- command:skills/loop-test/commands/auto-test-pages.md
- command:skills/loop-test/commands/auto-test-pytest.md
- command:skills/loop-test/commands/auto-test-webmcp.md
_source_fingerprint: 1f7d00e14600bd024cce33c5bb5866b467da97656301459b656447ad070ab5a2
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:17:12Z'
_cites:
- '[[command:skills/loop-quality/commands/auto-format.md]]'
- '[[command:skills/loop-quality/commands/auto-lint.md]]'
- '[[command:skills/loop-quality/commands/auto-ui-quality.md]]'
- '[[command:skills/loop-quality/commands/auto-yaml-lint.md]]'
- '[[command:skills/loop-test/commands/auto-e2e-actions.md]]'
- '[[command:skills/loop-test/commands/auto-e2e-pipeline.md]]'
- '[[command:skills/loop-test/commands/auto-test-api.md]]'
- '[[command:skills/loop-test/commands/auto-test-build.md]]'
- '[[command:skills/loop-test/commands/auto-test-dashboard.md]]'
- '[[command:skills/loop-test/commands/auto-test-links.md]]'
- '[[command:skills/loop-test/commands/auto-test-mcp-commands.md]]'
- '[[command:skills/loop-test/commands/auto-test-mcp.md]]'
- '[[command:skills/loop-test/commands/auto-test-pages.md]]'
- '[[command:skills/loop-test/commands/auto-test-pytest.md]]'
- '[[command:skills/loop-test/commands/auto-test-webmcp.md]]'
_mentions:
- '[[concepts/operational-audit-and-observability-commands]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
_relates_to:
- '[[adaptive]]'
- '[[command]]'
- '[[loops]]'
- '[[operational-audit-and-observability-commands]]'
- '[[platform-admin-and-skill-quality-commands]]'
- '[[quality]]'
- '[[testing]]'
_entity_tier: 2
---

# Testing And Quality Command Loops

## Compiled truth

### Current Thesis

Testing and quality commands define Augur's verification ladder. They are useful because they let an agent escalate from the cheapest safe checks to the slower end-to-end proofs that actually protect user-visible behavior.

### What This Page Knows

The commands in this cluster cover the full validation stack: formatting and lint repair, YAML hygiene, page and link resolution, API health, MCP registration, dashboard builds, Python and Jest suites, WebMCP checks, and end-to-end read and write-path validation. The durable rule is sequencing. Start with fast structural checks, then prove integration boundaries, and finish with the E2E paths that confirm real dashboard and tool behavior rather than only local code style.

### Key Dimensions

- End-to-end validation for vault-to-dashboard reads and mutation round trips when user-visible confidence matters.
- Fast automatic cleanup such as formatting and lint autofix before deeper investigation.
- Framework-level test execution across Python, dashboard Jest, build, and WebMCP surfaces.
- Structural verification over routes, links, API endpoints, and MCP tool visibility.

### Recent Shifts

- The command set now treats MCP and WebMCP coverage as first-class verification work instead of peripheral infrastructure checks.
- Write-path E2E coverage makes quality loops less about static correctness and more about proving real product workflows.

### Open Tensions

- Autofix commands save time, but they can hide underlying design drift if agents stop after the first green run.
- Running the whole ladder on every change is expensive, so command selection has to match risk instead of becoming ritual.

### How to Use This

Use this page when deciding which proof is necessary before claiming a change is correct. Reach for these commands when you need evidence that a page builds, routes resolve, tools register, tests pass, or an end-to-end flow still works. For repository-wide diagnosis and release coordination, connect this family with [[concepts/platform-admin-and-skill-quality-commands]] and [[concepts/operational-audit-and-observability-commands]].

### Open Questions

- How should UI-quality audits balance broad automated scanning with real browser verification on the affected worktree?
- Which checks should stay lightweight smoke tests and which should graduate into mandatory end-to-end proof for merge-critical paths?

### Source Basis

- `command:skills/loop-quality/commands/auto-format.md`: Run Prettier formatting on source files.
- `command:skills/loop-quality/commands/auto-lint.md`: Run ESLint auto-fix first, then surface unresolved diagnostics for guided repair.
- `command:skills/loop-quality/commands/auto-ui-quality.md`: Run the UI quality audit across dashboard pages, score the problems, and apply.
- `command:skills/loop-quality/commands/auto-yaml-lint.md`: Lint YAML configuration files for syntax errors, formatting drift, duplicate keys, and deep nesting.
- `command:skills/loop-test/commands/auto-e2e-actions.md`: Run the write-path E2E validator for action wiring, MCP mutations, and readback.
- `command:skills/loop-test/commands/auto-e2e-pipeline.md`: Run the end-to-end pipeline validator from vault data through RAG, MCP, API, and dashboard rendering.
- `command:skills/loop-test/commands/auto-test-api.md`: Run API route health checks used by the nightly testing loop.
- `command:skills/loop-test/commands/auto-test-build.md`: Run the dashboard build verification loop.
- `command:skills/loop-test/commands/auto-test-dashboard.md`: Run the dashboard Jest smoke and scoped test loop.
- `command:skills/loop-test/commands/auto-test-links.md`: Run the internal dashboard link scanner.
- `command:skills/loop-test/commands/auto-test-mcp-commands.md`: Run categorized MCP command coverage checks.
- `command:skills/loop-test/commands/auto-test-mcp.md`: Run MCP connectivity and tool-registration checks.

### Related Concepts

- [[concepts/operational-audit-and-observability-commands]]
- [[concepts/platform-admin-and-skill-quality-commands]]

## Timeline

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-quality/commands/auto-format.md
  Run Prettier formatting on source files.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-quality/commands/auto-lint.md
  Run ESLint auto-fix first, then surface unresolved diagnostics for guided repair.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-quality/commands/auto-ui-quality.md
  Run the UI quality audit across dashboard pages, score the problems, and apply.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-quality/commands/auto-yaml-lint.md
  Lint YAML configuration files for syntax errors, formatting drift, duplicate keys, and deep nesting.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-test/commands/auto-e2e-actions.md
  Run the write-path E2E validator for action wiring, MCP mutations, and readback.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-test/commands/auto-e2e-pipeline.md
  Run the end-to-end pipeline validator from vault data through RAG, MCP, API, and dashboard rendering.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-test/commands/auto-test-api.md
  Run API route health checks used by the nightly testing loop.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-test/commands/auto-test-build.md
  Run the dashboard build verification loop.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-test/commands/auto-test-dashboard.md
  Run the dashboard Jest smoke and scoped test loop.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-test/commands/auto-test-links.md
  Run the internal dashboard link scanner.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-test/commands/auto-test-mcp-commands.md
  Run categorized MCP command coverage checks.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/loop-test/commands/auto-test-mcp.md
  Run MCP connectivity and tool-registration checks.
