---
status: Implemented
date: 2026-04-09
deciders:
  - Gur Sannikov
related: []
hub: null
tags:
  - skills
  - catalog
  - cleanup
superseded_by: null
---

# ADR-580: Skill Catalog Minimization

## Context

The `skills/` tree mixed several different concerns: user-facing standalone skills, Augur-internal support skills, lightly-modified external imports, and overlapping skills that should be merged or removed. This made the standalone skill catalog noisy and weakened the public installation story.

A first-pass audit identified weak boundaries (`post`, `design-content-pipeline`, `scrape-and-save-idea`), thin internal skills (`hub-template`, `skill-setup`, `performance-profiling`, `nightly`), real product migrations (`linkedin-writer` into `content`, `wearables` into `health`, `wealth` into `finance`, `enterprise` into `venture`), concept-target migrations awaiting destination skills (`books`/`reading-list` → `reading`, `growth` → `learning`), and externalization candidates (`generative-ui`, `career-ops`).

The audit also surfaced infrastructure drift: `src/mcp/augur_mcp/domain/reviews.py` was a thin shim dynamically loading `skills/channels/augur/lib/registry.py`, indicating the review queue actually belonged to `channels` rather than core domain.

The objective is to minimize the Augur-owned core to the smallest coherent set without deleting real runtime behavior, while introducing a single explicit `augur-internal` catalog category to separate internal-only skills from public standalone products.

## Decision

Adopt a two-axis review model — Catalog (`public` vs `augur-internal`) and Ownership (`augur`, `adopted`, `external-candidate`) — and execute the consolidation in phased waves:

1. **Phase 1 (Thin Wrapper Merges):** absorb `post`, `design-content-pipeline`, `scrape-and-save-idea` into stronger destinations.
2. **Phase 2 (Infrastructure Ownership Cleanup):** move review tooling fully into `channels`, retire the `src/mcp/augur_mcp/domain/reviews.py` shim, clean stale `executor` wiring.
3. **Phase 3 (Thin Internal Boundary Reduction):** consolidate or remove `hub-template`, `skill-setup`, `performance-profiling`, `nightly`.
4. **Phase 4 (Direct Absorption Migrations):** migrate `linkedin-writer` → `content`, `wearables` → `health`, `wealth` → `finance`, `enterprise` → `venture` (renaming `venture-augur` to `venture`).
5. **Phase 5 (Concept-Target Migrations):** create real `reading` and `learning` destinations before merging `books`/`reading-list`/`growth`.
6. **Phase 6 (Externalization):** plan deliberate exits for `generative-ui` and `career-ops`.

For every destructive move, check MCP tools, pages, generated blocks, tests, docs, and cross-repo references first. Prefer absorbing weak boundaries into stronger destination skills before removing files. Keep tool names stable during migrations.

## Consequences

### Positive
- Standalone catalog shrinks to a coherent, understandable set of user-installable products.
- Clear `augur-internal` category hides plumbing skills from the public catalog without deleting them.
- Infrastructure drift (review queue shim) is corrected: `channels` becomes a real internal infrastructure skill.
- Migration ordering minimizes risk: obvious deletions first, real product migrations later.
- Hub structure remains independent of skill packaging decisions (no forced hub-skill alignment).

### Negative
- Multi-phase execution stretches across many commits; partial states will exist mid-migration.
- Concept-target migrations (`reading`, `learning`) are blocked until destination skills are created.
- Tool-name stability constraint adds friction to redesigning ergonomically-named replacements during a migration.
- Cross-repo reference sweeps (vault, docs, generated blocks) add audit overhead per skill removed.

### Neutral
- Hubs remain orthogonal to skills; reduction is catalog-only.
- Externalized skills (`generative-ui`, `career-ops`) still ship somewhere — the change is ownership flip, not deletion.

## Alternatives Considered

### Alternative 1: One-pass mass deletion based on the audit
Delete everything flagged weak in a single batch. Rejected because some thin-looking skills (e.g. `channels`) actually own real runtime behavior; a one-pass approach would shed real features along with catalog noise.

### Alternative 2: Replace hubs with a skill taxonomy
Use the audit as an excuse to redesign the public catalog around hubs. Rejected as out of scope — hubs are cross-skill user workspaces and should remain independent of skill packaging decisions.

### Alternative 3: Skip the `augur-internal` category and rely on metadata heuristics
Infer internal-vs-public from skill name patterns (`auto-*`, `runbook-*`). Rejected because heuristics drift; an explicit `x-augur-category` field makes the boundary auditable and stable.

## References
- Plan: docs/superpowers/plans/2026-04-09-skill-catalog-minimization-execution.md
- Spec: docs/superpowers/specs/2026-04-08-skill-catalog-minimization-audit-design.md
