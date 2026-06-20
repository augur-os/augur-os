---
title: Daemon Maintenance Command Loops
summary: Daemon-owned command surfaces that keep background services, adaptive loops,
  self-heal flows, and repo hygiene running safely.
tags:
- daemon-maintenance-command-loops
- adaptive-loop-maintenance-surfaces
- operational-audit-and-observability-commands
- platform-admin-and-skill-quality-commands
- command
- daemon
- maintenance
- loops
aliases: []
related:
- '[[adaptive-loop-maintenance-surfaces]]'
- '[[operational-audit-and-observability-commands]]'
- '[[platform-admin-and-skill-quality-commands]]'
created: '2026-04-23T10:19:48Z'
_page_type: concept
_hub: command
_sources:
- command:skills/daemon/commands/auto-code-health.md
- command:skills/daemon/commands/auto-heal-validate.md
- command:skills/daemon/commands/auto-mcp-hygiene.md
- command:skills/daemon/commands/auto-security-scan.md
- command:skills/daemon/commands/auto-self-heal.md
- command:skills/daemon/commands/auto-skill-md.md
- command:skills/daemon/commands/auto-skill-refs.md
- command:skills/daemon/commands/auto-stale-paths.md
- command:skills/daemon/commands/dev-loops.md
- command:skills/daemon/commands/ops-daemon.md
- command:skills/daemon/commands/test-heal.md
_source_fingerprint: c8e953b02699e48a5e3683034a53955149601d8c1a0d0618ee59d05cb852c2c2
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:17:12Z'
_cites:
- '[[command:skills/daemon/commands/auto-code-health.md]]'
- '[[command:skills/daemon/commands/auto-heal-validate.md]]'
- '[[command:skills/daemon/commands/auto-mcp-hygiene.md]]'
- '[[command:skills/daemon/commands/auto-security-scan.md]]'
- '[[command:skills/daemon/commands/auto-self-heal.md]]'
- '[[command:skills/daemon/commands/auto-skill-md.md]]'
- '[[command:skills/daemon/commands/auto-skill-refs.md]]'
- '[[command:skills/daemon/commands/auto-stale-paths.md]]'
- '[[command:skills/daemon/commands/dev-loops.md]]'
- '[[command:skills/daemon/commands/ops-daemon.md]]'
- '[[command:skills/daemon/commands/test-heal.md]]'
_mentions:
- '[[concepts/adaptive-loop-maintenance-surfaces]]'
- '[[concepts/operational-audit-and-observability-commands]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
_relates_to:
- '[[adaptive-loop-maintenance-surfaces]]'
- '[[command]]'
- '[[daemon]]'
- '[[loops]]'
- '[[maintenance]]'
- '[[operational-audit-and-observability-commands]]'
- '[[platform-admin-and-skill-quality-commands]]'
_entity_tier: 2
---

# Daemon Maintenance Command Loops

## Compiled truth

### Current Thesis

Daemon maintenance commands are the operating layer that keeps Augur alive between interactive sessions. They own service lifecycle, loop execution, trust-gated automation, and the recurring health checks that have to keep running even when no one is actively editing the repo.

### What This Page Knows

This cluster combines background-service control commands such as `ops-daemon`, `loop-status`, and `run-loop-cycle` with recurring hygiene loops for self-heal, MCP naming, page mounts, stale paths, repository sync, performance, and security. Read together, the pattern is clear: these commands are not feature workflows. They are the runtime control plane for making sure autonomous maintenance, notifications, and service-level checks keep operating without drifting into silent failure.

### Key Dimensions

- Adaptive loop inspection, promotion, and targeted execution through loop status and trust-gated controls.
- Continuous hygiene over MCP registration, page mounts, stale paths, skill docs, security, and performance.
- OS-level daemon lifecycle and service ownership rather than one-off repo scripts.
- Self-heal and notification flows that turn runtime errors into repairable operational work instead of dead logs.

### Recent Shifts

- Loop control and daemon status have become the canonical surface for autonomous maintenance instead of ad hoc shell entrypoints.
- More repository and runtime hygiene checks are now daemon-managed, which moves operational knowledge into long-lived maintenance commands.

### Open Tensions

- A daemon-owned check has to stay safe enough for unattended execution while still surfacing actionable repairs.
- The cluster can become too broad if lifecycle controls, observability audits, and repo hygiene are not kept as distinct neighboring concepts.

### How to Use This

Use this page when the question is about background runtime behavior, autonomous repair, or why a recurring maintenance surface exists at all. Start here before dropping into a specific command because the useful distinction is whether the task belongs to daemon-owned service health, to interactive debugging, or to a higher-level admin workflow such as [[concepts/platform-admin-and-skill-quality-commands]].

### Open Questions

- How much automatic remediation is safe before a daemon command should stop and hand the work back to an interactive agent?
- Which observability checks should stay daemon-owned versus move under the explicit audit surfaces in [[concepts/operational-audit-and-observability-commands]]?

### Source Basis

- `command:skills/daemon/commands/auto-code-health.md`: Unified code health monitoring — TypeScript build errors and API route health.
- `command:skills/daemon/commands/auto-heal-validate.md`: Validate self-heal daemon health and clear stuck journal entries.
- `command:skills/daemon/commands/auto-mcp-hygiene.md`: Per-plugin MCP tool naming, registration, dead-tool, and duplicate audit.
- `command:skills/daemon/commands/auto-security-scan.md`: Scan the codebase for hardcoded secrets and dependency vulnerabilities.
- `command:skills/daemon/commands/auto-self-heal.md`: Scan external Augur logs for errors and auto-fix them via `ai_self_healer`.
- `command:skills/daemon/commands/auto-skill-md.md`: Validate and generate SKILL.
- `command:skills/daemon/commands/auto-skill-refs.md`: Validate and fix SKILL.
- `command:skills/daemon/commands/auto-stale-paths.md`: ADR-270 enforcement scan for active code, workflows, and operational docs.
- `command:skills/daemon/commands/dev-loops.md`: Manage the Adaptive Loop Engine from the daemon runtime.
- `command:skills/daemon/commands/ops-daemon.md`: Manage the Augur unified daemon as an OS-level background service.
- `command:skills/daemon/commands/test-heal.md`: End-to-end verification that the self-heal pipeline (ADR-076 + ADR-084) works correctly.

### Related Concepts

- [[concepts/adaptive-loop-maintenance-surfaces]]
- [[concepts/operational-audit-and-observability-commands]]
- [[concepts/platform-admin-and-skill-quality-commands]]

## Timeline

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/auto-code-health.md
  Unified code health monitoring — TypeScript build errors and API route health.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/auto-heal-validate.md
  Validate self-heal daemon health and clear stuck journal entries.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/auto-mcp-hygiene.md
  Per-plugin MCP tool naming, registration, dead-tool, and duplicate audit.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/auto-security-scan.md
  Scan the codebase for hardcoded secrets and dependency vulnerabilities.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/auto-self-heal.md
  Scan external Augur logs for errors and auto-fix them via `ai_self_healer`.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/auto-skill-md.md
  Validate and generate SKILL.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/auto-skill-refs.md
  Validate and fix SKILL.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/auto-stale-paths.md
  ADR-270 enforcement scan for active code, workflows, and operational docs.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/dev-loops.md
  Manage the Adaptive Loop Engine from the daemon runtime.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/ops-daemon.md
  Manage the Augur unified daemon as an OS-level background service.

- _at: 2026-05-03T13:17:12Z  _source: command:skills/daemon/commands/test-heal.md
  End-to-end verification that the self-heal pipeline (ADR-076 + ADR-084) works correctly.
