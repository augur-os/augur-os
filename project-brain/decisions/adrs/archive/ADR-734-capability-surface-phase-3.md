---
status: Implemented
date: 2026-05-12
deciders:
  - gsannikov
related:
  - ADR-635
  - ADR-638
  - ADR-728
hub: command
tags:
  - capability-inventory
  - exposure-policy
  - mcp
  - skills
  - browse
  - drift-prevention
  - ai-clients
superseded_by: null
spec_file: 2026-05-12-capability-surface-phase-3-design.md
plan_file: 2026-05-12-capability-surface-phase-3.md
---

# ADR-734: Capability Surface Phase 3 — Cleanup Closure, Drift Guardrails, and Browse Control Hub

> **ADR-734 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Extend ADR-635 and ADR-638 with a final Phase 3 that closes remaining skills/MCP/CLI/client-surface cleanup, adds drift guardrails so generated Augur exports cannot recreate capability blowout, and makes Browse the unified control hub for current exposure, intended exposure, launch affordances, Draft-tab leftovers, and reviewed policy actions.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-12-capability-surface-phase-3-design.md`](../superpowers/specs/2026-05-12-capability-surface-phase-3-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-12-capability-surface-phase-3.md`](../superpowers/plans/2026-05-12-capability-surface-phase-3.md) — 7 checkpoints across 3 spec tracks: C1 inventory baseline + "what remains" report; C2 eight-dimension drift guardrails (direct MCP, unclassified, blocked-present, unexpected-client, duplicate-external, draft-leakage, AGENTS.md drift, Gemini/OpenCode budget blowout) plus aggregator CLI and auto-loop; C3 generated-surface cleanup + skill-stub drift detector mirroring the existing command-stub one; C4 external duplicate classification with `multi_client_approved` policy field; C5 Drafts-tab behavior and regression guard against draft leakage into client skill dirs; C6 Browse control-hub fields, launcher actions, MCP-mediated policy-action drafts, impact previews, and unmanaged-path approval gate; C7 snapshot tests, browser verification, full auto-loop pass, and ADR status flip. TDD discipline throughout: every code-adding task is failing-test → minimal-impl → passing-test → commit.

## Status notes

Accepted after a focused brainstorming pass on 2026-05-12. Spec passed self-review; implementation plan written 2026-05-12 in the same session via `/superpowers:writing-plans` (Codex's original ADR-734 commit `7d3d1ab84` skipped the planning step; this ADR was re-pointed at the plan in a follow-up Claude session to align with the new spec → plan → ADR workflow). Current capability exposure policy is already broadly classified and reduced; this ADR records what remains: cleanup closure, regression guardrails, and Browse control-hub completion.

Load-bearing claims:

- **ADR-635/638 remain the foundation.** This ADR does not replace the inventory, policy overlay, resolver, or Browse control-plane direction. It defines the closure phase on top of them.
- **Generated Augur surfaces are enforceable; unmanaged external surfaces are report-first.** The cleanup may remove or regenerate Augur-owned generated output according to policy, but unmanaged external/global folders require explicit approval before physical deletion.
- **Browse is the PC hub.** The user should be able to see what exists, where it is exposed, what policy intends, how to launch it, and what cleanup remains without reading generated client configs by hand.
- **Guardrails must distinguish failure from drift warning.** Augur-generated violations should fail tests or loops. External unmanaged drift should stay visible and actionable without destructive automation.

## Related

- ADR-635 — Capability Inventory Exposure Policy
- ADR-638 — Capability Inventory Control Plane
- ADR-728 — Browse Page Lifecycle Ordering and Journey-Group Delimiters

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated:
    - broad direct generated AI-client exposure without capability policy
    - hidden staged or draft leftovers acting as active capabilities
  files_affected:
    - config/system/capability_exposure.yaml
    - apps/dashboard/app/(views)/browse/
    - src/lib/capabilities/
    - shared-vault/skills/ai/scripts/sync_agents/
```
