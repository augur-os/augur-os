---
status: Implemented
date: 2026-05-25
deciders:
  - gsannikov
related: [781, 783, 784, 785, 786]
hub: null
tags: [multi-brain, harness, projection, client-sync, merge, sync-agents]
superseded_by: null
spec_file: 2026-05-25-harness-layering-family-design.md
plan_file: 2026-05-25-harness-c1b-verify-harness.md
---

# ADR-782: C1 — Capability Projection & Client Sync

> Child of the **ADR-781** harness-layering family. Canonical design: [`2026-05-25-harness-layering-family-design.md`](../superpowers/specs/2026-05-25-harness-layering-family-design.md).

## Decision summary

Consume the layered merge engine (`resolve_layered_projection`) to project instructions / slash commands / skills / subagents / MCP servers into every AI client via the **3-into-2 collapse** (Global⊕User → client HOME, Project → client REPO), most-specific-wins, with sync-safety for non-Augur entries and a **parity-gated cutover** from the single-brain path.

## C1 slice plans

C1 is implemented as ordered slices, each its own `docs/superpowers/plans/` plan:

| Slice | Plan | Status |
|---|---|---|
| C1a · effective/shadowed resolver (§2d) | `2026-05-25-harness-c1a-effective-shadowed-resolver.md` | ✅ done (`src/lib/brain_effective.py`) |
| C1b · `verify-harness` gate (§2a) | `2026-05-25-harness-c1b-verify-harness.md` | ✅ done (`src/lib/brain_verify_harness.py`) |
| C1c · source unification + per-call multi-tier + parity | `2026-05-25-harness-c1c-source-unification-parity.md` | ✅ done (`get_managed_skill_source_dirs`, parity gate, sync cutover) |
| C1d · 3→2 collapse + gated home-dir writes (outward-facing) | `2026-05-25-harness-c1d-collapse-gated-home-writes.md` | ✅ done (`AUGUR_HOME_SYNC` gate + home/repo partition) |

> Run C1 in one session in order: C1b (`plan_file`) → C1c → C1d. Each slice plan is self-contained.

## Context

Today `sync_agents` resolves capability sources from **module-level single-brain constants** (`constants.py` `SOURCE_RULES/SKILLS/WORKFLOWS/TOPICS`), there are **two divergent skill-source resolvers** (`resolve_brain_projection_sources` vs `get_managed_skill_source_dirs`), and skills/commands/agents are written to **REPO only** (only rules/MCP reach HOME for a couple of clients). This cannot express the User tier projecting machine-wide into every client. This is the largest single refactor in the family and the primary cross-client-correctness surface.

## Decision

1. Refactor the module-level single-brain source constants → **per-call multi-tier resolution** fed by `resolve_layered_projection(stack)`.
2. **Unify the two skill-source resolvers** into one tier-aware source.
3. Implement the **3→2 collapse**: pre-merge Global⊕User → client HOME (`~/.claude`, `~/.codex`, `~/.gemini`); Project → client REPO; client enforces repo ⊐ home.
4. Compute **effective/shadowed** via the shared pure resolver (781 §2d); flag shadowed instances.
5. **Sync-safety:** only Augur-managed entries are written/removed; non-Augur files in client dirs are never clobbered.
6. **Home-dir writes are gated** — explicit opt-in/confirm; never a silent default (outward-facing).
7. **Parity-gated cutover** (781 §2c): flip single-brain → layered only after parity proves layered ≥ single-brain for the current active brain; delete the old path *after* parity passes.

## Completion gate

`verify-harness` (781 §2a) green on real Claude/Codex/Gemini with real data — non-empty, correctly-merged, precedence honored, pages/skills/commands load (rules 28/34); non-Augur entries verified untouched; parity check passed before cutover.

## Status notes

Implemented on 2026-05-25. C1c routes managed skill source discovery through the layered brain stack for live/project brain roots while preserving isolated temp-root behavior for tests. C1d adds the 3→2 home/repo partition with explicit `AUGUR_HOME_SYNC` opt-in, projects User/Home skills to the global client skill dirs, and keeps Project-tier repo projection available for local client dirs.

Closeout evidence from the real home-sync gate: `AUGUR_HOME_SYNC=1` wrote 23 Augur-managed skills to Claude, Codex, Gemini, Copilot, and OpenCode global targets; parity passed with no drops (`added=[books, file-manager, vault]`); `verify_harness_summary` returned `all_ok: true` for Claude/Codex/Gemini; pre-existing non-managed home files were byte-stable after sync (Claude 34 files, Codex 49 files).

## Consequences

**Positive:** the User tier finally projects machine-wide into every client; one shared resolver removes per-adapter divergence; the two-resolver tangle is retired. **Negative:** large refactor of the generation pipeline; home-dir writes touch the user's global client config (mitigated: gated + parity + verify-harness). **Neutral:** REPO projection for the Project tier is unchanged in shape.

## Dependencies

ADR-781 shared infra (merge engine ✅, effective/shadowed resolver, `verify-harness`, parity gate). Blocks C2–C5.

## References

- ADR-781 (parent) · family spec · ADR-490 (dashboard import architecture)
- `project-brain/capabilities/skills/ai/scripts/sync_agents/` (`engine.py`, `constants.py`, `skill_sync.py`, `command_surface.py`, `adapters/`)
