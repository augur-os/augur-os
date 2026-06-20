---
status: Implemented
date: 2026-04-14
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-586: Documentation Convergence

## Context

The `augur` repo's external-facing documentation has drifted into contradictory states across top-level docs (`README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`) and the deeper `docs/` tree. Some docs imply a broader public release than reality; others use stale launch language, leave visible TODO placeholders, or contradict the platform support story. There is no canonical `ROADMAP.md` in `augur` — roadmap and launch-state messaging only exist in the public mirror.

The current real state is: Augur is in soft launch, native macOS support is implemented, native Windows architecture is implemented, but Windows validation is still pending before a firmer public support claim, and release planning is active.

This is a documentation-only convergence pass, not a product implementation pass. The goal is to remove contradictory or stale messaging so the docs in `augur` can later be published into `augur-os` through a deploy command, without hand-editing two separate documentation sets.

## Decision

Make `augur` the canonical documentation source for the project's external-facing story. Treat docs touched in this pass as external-facing by default. Specifically:

1. Rewrite `README.md` so the current state, platform status, and soft-launch posture are explicit. Remove visible placeholders.
2. Add `ROADMAP.md` at the repo root with the canonical release direction (soft launch now, May 2026 MVP target, monthly release direction afterward, Windows validation pending). Roadmap framing is provisional and non-contractual during soft launch.
3. Align `CONTRIBUTING.md`, `SECURITY.md`, and `CHANGELOG.md` so the opening reflects the same state — no overclaiming, no stale support-matrix wording.
4. Align deeper guides and references (`docs/getting-started.md`, `docs/developer-guide.md`, `docs/guides/installation-windows.md`, `docs/architecture-overview.md`, plus any `docs/**/*.md` discovered during sweep) where they make external claims.
5. Run a contradiction sweep (`rg`) across markdown for stale placeholders, platform wording contradictions, and install/readiness overclaims.

Out of scope: code, scripts, config, CI, runtime behavior, the actual deploy command into `augur-os`, and rewriting internal markdown that does not make external claims.

## Consequences

### Positive
- One coherent external narrative across top-level docs
- Top-level `ROADMAP.md` exists in `augur` and removes the public-mirror-only roadmap state
- Platform messaging is consistent wherever it appears
- Future publishing into `augur-os` requires far less editorial work

### Negative
- Some intentional depth may risk being trimmed during convergence; mitigated by converging wording rather than shortening across the board
- Roadmap is provisional — must be updated as release timing evolves

### Neutral
- No code, config, or runtime behavior changes
- Internal-only docs that make no external claims remain untouched

## Alternatives Considered

### Alternative 1: Top-level docs only
Converge only `README.md` and add `ROADMAP.md`, leaving deeper docs as-is. Rejected: future public publishing would still inherit contradictions from guides and references.

### Alternative 2: Defer until deploy command exists
Wait until the `augur` → `augur-os` deploy command is designed before converging docs. Rejected: drift compounds, and convergence is a prerequisite for any clean deploy.

## References
- Plan: docs/superpowers/plans/2026-04-14-documentation-convergence.md
- Spec: docs/superpowers/specs/2026-04-14-documentation-convergence-design.md
