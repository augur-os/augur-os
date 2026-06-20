---
status: Implemented
date: 2026-05-21
deciders:
  - gsannikov
related: [ADR-754, ADR-768, ADR-769, ADR-770]
hub: brain
tags: [brain, ai-clients, projections, write-routing, memory]
superseded_by: null
spec_file: 2026-05-21-brain-client-projections-write-routing-design.md
plan_file: 2026-05-21-brain-client-projections-write-routing.md
---

# ADR-771: Brain Client Projections And Write Routing

> **ADR-771 is an index file.** The substantive design and implementation steps
> live in the linked spec + plan. This file carries pointers, status, and a
> one-line decision summary.

## Decision summary

Make brain-owned instructions/capabilities canonical for generated AI-client
projections and route writes through explicit brain destination rules.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-21-brain-client-projections-write-routing-design.md`](../superpowers/specs/2026-05-21-brain-client-projections-write-routing-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-21-brain-client-projections-write-routing.md`](../superpowers/plans/2026-05-21-brain-client-projections-write-routing.md)

## Status notes

Accepted 2026-05-21. Implemented 2026-05-21.

Tasks 1–3 (projection source abstraction, sync-adapter brain sourcing, and the
per-client `augur:` context envelope) landed with the ADR-769 foundation:
`src/lib/brain_projection.py` resolves brain-owned canonical roots,
`sync_agents/constants.py:_discover_source_paths()` reads from them, and every
adapter injects `render_augur_context_envelope()` (verified live in CLAUDE.md,
AGENTS.md, CODEX.md, `.gemini/GEMINI.md`, `.github/copilot-instructions.md`,
`.opencode/AGENTS.md`).

This ADR completed Tasks 4–5: `/ingest` (`inbox-consume-folder` →
`consume_folder`) now routes through `resolve_write_target` with `--to`/cwd and
rejects packets-only brains, and `promote-browse-item` now creates explicit,
source-contained `<source-brain> -> <target-brain>` propagation packets in the
target brain's promotions inbox while keeping the legacy private→shared path
unchanged. `/note`, `/save`, and `/ask retain` were already brain-routed.

Implemented ahead of ADR-770: the projection resolver explicitly handles the
physical-migration window (it maps `docs/agent-topics` and legacy
`shared-vault/skills` while `project-brain/` does not yet exist), so this phase
is forward-compatible — once ADR-770 physically migrates files, the resolver
picks up the canonical `project-brain/` paths automatically with no further
change here.

## Related

- ADR-770: Physical project-brain migration.
- ADR-772: UI and memory review surfaces that expose this routing.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "sync_agents source resolution reads brain-owned canonical roots"
    - "write commands accept or route through brain destination context"
  patterns_deprecated:
    - "client-native instruction files as canonical sources"
    - "implicit memory writes from /note or /ask"
  files_affected:
    - "shared-vault/skills/ai/scripts/sync_agents/*"
    - "shared-vault/skills/augur-core/commands/*"
    - "src/lib brain context/routing helpers"
    - "MCP write tools for note/save/ingest/ask retain"
```

## Implementation Prompt

To execute this ADR, run:

```text
/adr implement ADR-771
```
