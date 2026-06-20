---
status: Implemented
date: 2026-05-25
deciders:
  - gsannikov
related: [781, 782, 783, 784, 786, 490]
hub: null
tags: [multi-brain, harness, dashboard, manager, ui, effective-shadowed]
superseded_by: null
spec_file: 2026-05-25-harness-layering-family-design.md
plan_file: 2026-05-25-harness-c4-manager-surface.md
---

# ADR-785: C4 — Harness Manager Surface

> Child of the **ADR-781** harness-layering family. Canonical design: [`2026-05-25-harness-layering-family-design.md`](../superpowers/specs/2026-05-25-harness-layering-family-design.md).

## Decision summary

A VS-Code-settings-style **harness manager** dashboard surface: a tier filter (Global / User / Project / Effective), per-capability rows showing owner badge + tier + effective/shadowed status, and Promote/Demote actions — the sanctioned rule-32 interactive-manager exception (not a Browse card tab).

## Status notes

Implemented 2026-05-25. `src/lib/brain_manager_snapshot.py` now produces the
tiered effective/shadowed manager model across skills, instructions, commands,
subagents, MCP, memory, profile, and knowledge, with promote/demote operations
guarded by `verify-harness`. The dashboard renders the manager at
`/brain/harness` using the existing MCP route. Browser verification loaded
`http://localhost:3004/brain/harness`, showed the real stack with 278
effective rows and 0 shadowed overrides, and `/api/skill-meta/vault` returned
the private-vault skill as healthy with no console errors.

## Context

With layering live (C1–C3), users need to *see* and *manage* what each tier contributes and which instance wins. The model is the VS Code settings editor: Default / User / Workspace columns with the effective value and override indicators, plus "copy to user/workspace." Browse rule 32 reserves bespoke manager surfaces for genuine install/configure/manage consoles — this qualifies.

## Decision

1. **Tier filter** — Global · User · Project · **Effective** (the merged result the agent actually sees).
2. **Capability rows** — owner badge (`claude-native` / `augur` / …), tier, and **effective vs shadowed** (overridden instances linked to the winner), grouped by capability type (instructions, commands, skills, subagents, MCP, `aug` subcommands, memory, profile, knowledge).
3. **Actions** — `Promote` (client-native → Augur-managed, landing tier per the 781 ladder) and `Demote/Eject` (Augur-managed → single client).
4. **Data source** — extend `build_discovery_snapshot` for the full stack; reuse the shared effective/shadowed resolver (781 §2d) — no bespoke logic.

## Completion gate

Real-browser client-load verification (rule 28); shows correct effective/shadowed for the real stack; Promote/Demote round-trip works and is reflected by `verify-harness`.

## Consequences

**Positive:** the layering becomes legible and manageable; "why did this client get X from tier Y" is answerable in one click. **Negative:** depends on C1–C3 being correct first. **Neutral:** follows the established dashboard MCP-only data-flow (rule 11).

## Dependencies

C1, C2, C3 (the data it visualizes), ADR-781 shared resolver. Blocks C5.

## References

- ADR-781 (parent) · ADR-490 (dashboard import architecture) · `docs/architecture-dashboard.md` (rule 32) · family spec
- `src/lib/brain_discovery.py` (`build_discovery_snapshot`)
