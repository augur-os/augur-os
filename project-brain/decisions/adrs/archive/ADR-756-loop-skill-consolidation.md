---
status: Implemented
date: 2026-05-16
deciders:
  - gsannikov
related:
  - ADR-601
  - ADR-755
  - ADR-727
hub: command
tags:
  - skills
  - consolidation
  - auto-loops
  - decentralization
superseded_by: null
spec_file: 2026-05-16-loop-skill-consolidation-design.md
plan_file: 2026-05-16-loop-skill-consolidation.md
---

# ADR-756: Loop-Skill Consolidation (`loop-*` → `routine-*` by concern)

## Status

Implemented.

## Context

The 11 `loop-*` skills under `shared-vault/skills/` (loop-test, loop-quality, loop-wiring, loop-ops, loop-docs, loop-repo, loop-hub-coverage, loop-observability, loop-memory, loop-security, loop-hygiene) carry 85 `auto-*.md` commands between them. The skill boundaries are historical artifacts of when each loop was first registered, not coherent ownership boundaries by concern:

- `loop-hygiene` has **zero** auto-commands (empty skill, leftover).
- `loop-security` has **one** auto-command.
- `loop-test` has 11; `loop-wiring` has 9; the spread is uneven.
- Several skills cross concerns: `loop-repo` contains both git health (platform) and vault hygiene (vault); `loop-docs` contains both doc freshness (vault) and skill-usage scans (coverage).

ADR-755 modernizes the auto-loop **runner**. It is deliberately scoped to not touch skill ownership — runner rewrite + skill reorganization at once is too many concurrent variables. This ADR is the follow-up that reorganizes the skill landscape **after** ADR-755 has landed and stabilized.

## Decision

Collapse 11 `loop-*` skills into 5 `routine-*` skills aligned by concern:

| New skill | Absorbs | Rationale |
|---|---|---|
| `routine-codebase` | `loop-test` + `loop-quality` + `loop-wiring` | All "is the codebase correct" work — tests, types, code quality, API/MCP/page wiring |
| `routine-vault` | `loop-memory` + vault-related auto-commands from `loop-repo` + vault-related auto-commands from `loop-docs` | Vault/knowledge hygiene — memory curation, vault repair, doc freshness |
| `routine-platform` | git-related auto-commands from `loop-repo` + `loop-ops` + `loop-observability` | Platform health — git, page health, metrics, plugin lint |
| `routine-security` | `loop-security` | Standalone; clear ownership |
| `routine-coverage` | `loop-hub-coverage` + skill-usage auto-commands from `loop-docs` | Cross-cutting coverage scans |

Retire `loop-hygiene` (zero auto-commands; nothing to migrate). Split `loop-docs` and `loop-repo` between two destination skills each (doc-freshness vs skill-usage; git vs vault).

Migration is per-auto-command: each `auto-*.md` + its `scripts/*_ops.py` module + its SKILL.md `x-augur-commands` declaration relocate to the destination skill, preserving the auto-command's name + scan/fix contract + loop-category mapping (`hardening`, `testing`, etc.). The `loop` category names in `adaptive_loops.yaml` are NOT renamed — only the *skill ownership* changes. This means `/dev-loops run testing` keeps running the same set of auto-commands, just discovered under different skill roots.

After migration:
- Every `auto-*.md` has a clear single-owner skill.
- Each new `routine-*` skill has a coherent concern statement in its SKILL.md.
- Cross-references to old `loop-*` paths in docs, scripts, and configs are updated.
- The 11 old `loop-*` skill directories are deleted (or moved to a deprecation archive).

## Non-Goals

- **Not renaming loop categories** (`testing`, `hardening`, `code-quality`, etc.). Loop categories are runtime concepts; skill names are organizational concepts. They're independent.
- **Not changing auto-command behavior**. Each `scan()` / `fix()` module moves verbatim.
- **Not changing the runner**. ADR-755 owns that. This ADR is purely organizational.
- **Not retiring `journal.jsonl`**. ADR-757 owns that.
- **Not introducing new auto-commands**. Migration is move-only.
- **Not changing `adaptive_loops.yaml`** beyond updating any per-skill paths if relevant.

## Consequences

- One clear ownership map for every auto-command. New contributors learn 5 skills instead of 11.
- `routine-*` naming aligns with the noun ADR-727 introduced and ADR-755's `routine_orchestrator` module.
- `loop-hygiene` (empty) retires cleanly; no auto-commands to migrate.
- Touches every loop-* skill — high blast radius if done sloppily, but each move is a mechanical `git mv` + frontmatter update.
- Cross-references in docs and scripts need updating (the migration plan enumerates every reference).
- One commit per skill migration keeps the history readable and revertable.
- After this ADR ships, `ls shared-vault/skills/ | grep routine-` shows 5 skills, and `ls shared-vault/skills/ | grep loop-` shows zero.
- Sync_agents regeneration must run after each skill migration to keep client-side projections coherent.

## Alternatives Considered

1. **Keep 11 skills, just rebuild the runner (ADR-755 only).** Rejected as a stopping point — leaves the historical-artifact skill landscape in place, which keeps confusing new contributors and fragments ownership.
2. **Collapse to fewer skills (3 instead of 5).** Considered: `routine-correctness` + `routine-knowledge` + `routine-platform-and-security`. Rejected — security has a different review/threat-modeling profile and deserves a clear single-owner skill; coverage is a cross-cutting concern that doesn't fit cleanly under any of the three.
3. **Collapse to more skills (rename 1-to-1 with new prefix only).** Rejected — preserves the historical fragmentation while adding the rename overhead. Worst of both worlds.
4. **Defer indefinitely; leave loop-* as is forever.** Rejected — ownership ambiguity is a real onboarding cost. While each individual auto-command works, the skill landscape is not coherent. A one-time cleanup pays for itself.

## Related

- ADR-601 (Skill directory layout)
- ADR-727 (Background Routines noun — this ADR finishes the noun-alignment at the skill level)
- ADR-755 (Auto-loop runner modernization — must land first; this ADR depends on the runner being stable)
- ADR-757 (Journal retirement — orthogonal, can land before or after this ADR)
- ADR-758 (Routines unification — depends on this ADR for the skill layer being stable)

---

## Implementation

Run `/adr implement ADR-756` from the intended active worktree, **after** ADR-755 is fully implemented and merged. The slash command reads this ADR's `plan_file`, reuses the current linked Augur worktree when invoked from one, creates a new implementation worktree only when invoked from the main checkout, and executes the per-skill migration tasks via `superpowers:subagent-driven-development`. The plan is structured so each of the 5 new skill creations is a parallel-safe teammate.

Implemented on 2026-05-16 in `adr-756-loop-skill-consolidation`. The live pre-migration audit found 46 registry-active `auto-*` routines, 53 command files, and 55 total command declarations/files rather than the 85 command-file assumption in the proposal. The implementation preserved the 46 registry-active routine ids exactly, including loop category, tier, and trigger metadata, while moving their owners to `routine-codebase`, `routine-platform`, `routine-vault`, `routine-coverage`, and `routine-security`.

The migration also preserved non-registry payload that mattered operationally. `loop-wiring` command files moved with `routine-codebase` but were not added to the active registry because they did not have top-level `x-augur-commands` before migration. `loop-ops` and `loop-test` script-backed declarations without command docs were preserved. `loop-hygiene` was not empty in the live checkout; it owned `/sweep-stores` plus archive/hygiene scripts, tests, fixtures, and references, all migrated under `routine-vault`.
