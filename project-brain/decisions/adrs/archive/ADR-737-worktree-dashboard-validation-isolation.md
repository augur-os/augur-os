---
status: Implemented
date: 2026-05-13
deciders:
  - gsannikov
related:
  - ADR-071
  - ADR-101
  - ADR-572
hub: dev
tags:
  - dashboard
  - worktrees
  - validation
  - lifecycle
  - self-heal
  - mcp
  - windows
superseded_by: null
spec_file: 2026-05-13-worktree-dashboard-validation-isolation-design.md
plan_file: 2026-05-13-worktree-dashboard-validation-isolation.md
---

# ADR-737: Worktree Dashboard Validation Isolation

> **ADR-737 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Introduce an Augur dashboard instance boundary so main remains the visible production/control-plane dashboard while each development worktree validates against its own lifecycle state, build lock, MCP port, browser profile, heal policy, and verification artifacts without navigating the main browser or sending IDE update prompts.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-13-worktree-dashboard-validation-isolation-design.md`](../superpowers/specs/2026-05-13-worktree-dashboard-validation-isolation-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-13-worktree-dashboard-validation-isolation.md`](../superpowers/plans/2026-05-13-worktree-dashboard-validation-isolation.md) - 8 tasks: dashboard instance resolver, preflight propagation, scoped lifecycle state, scoped build locks, visible-surface policy, validation-only self-heal, command workflow updates, and full verification.

## Status notes

Proposed 2026-05-13 after a worktree validation incident exposed that the existing dashboard lifecycle and heal paths still treat "the dashboard" as a single global runtime. The design has been approved for strict invisible worktree validation by default. Implementation is gated on the linked plan and must preserve main dashboard visibility while providing full worktree validation.

Load-bearing claims:

- Main checkout remains the only default visible dashboard surface: port 3000, MCP 8080, repair-capable self-heal, and user-visible recovery prompts.
- Worktree checkouts are validation instances: port 3001-3010, MCP 8081-8090, isolated/headless browser verification by default, and validation-only heal policy unless explicit repair is requested.
- Lifecycle state, gates, build locks, and browser artifacts must be keyed by resolved instance identity.
- Worktree validation failures must report evidence instead of mutating main state or moving the user's current browser tab.
- `/dev-merge full` must validate the source worktree before merge and main after merge, with distinct artifacts for both targets.

## Related

- ADR-071 - dashboard build concurrency and build-lock lineage.
- ADR-101 - original worktree isolation decision.
- ADR-572 - prior self-heal worktree skip gate that this ADR evolves into validation-only behavior.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "dashboard_lifecycle.py public API gains optional instance/project-root target parameters"
    - "worktree_preflight.py JSON output gains instance_id, instance_kind, browser_mode, heal_policy, visibility_policy, and scoped runtime paths"
    - "dashboard browser hooks gain a visible-surface policy guard before navigation or IDE prompt actions"
  patterns_deprecated:
    - "Single global dashboard lifecycle state for all checkouts"
    - "Worktree self-heal skip as the only safety behavior"
    - "Automatic worktree validation using the user's current visible browser tab"
  files_affected:
    - src/lib/dashboard_instance.py
    - scripts/dashboard_instance.py
    - scripts/worktree_preflight.py
    - apps/dashboard/lib/mcp/preflight.ts
    - apps/dashboard/scripts/start-dev.mjs
    - apps/dashboard/scripts/build-lock.mjs
    - apps/dashboard/lib/visible-surface-policy.ts
    - apps/dashboard/hooks/useMcpHealth.ts
    - shared-vault/skills/daemon/scripts/dashboard_lifecycle.py
    - shared-vault/skills/daemon/scripts/monitor/process.py
    - shared-vault/skills/daemon/scripts/cleanup_processes.py
    - shared-vault/skills/daemon/scripts/ops/self_heal.py
    - shared-vault/skills/platform-admin/commands/dev-build.md
    - shared-vault/skills/platform-admin/commands/dev-debug.md
    - shared-vault/skills/platform-admin/commands/dev-merge.md
```

