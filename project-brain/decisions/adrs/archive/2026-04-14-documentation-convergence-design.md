---
title: Documentation Convergence Design
date: 2026-04-14
status: proposed
owner: <user>
---

# Documentation Convergence Design

## Summary

Make `augur` the canonical documentation source for the project’s external-facing story.
The documentation surface should describe the real current state clearly: Augur is in soft launch, native macOS support is implemented, native Windows architecture is implemented, Windows validation is still pending before a firm public support claim, and the roadmap should show where the release process stands now.

This is a documentation convergence pass, not a product implementation pass.
The goal is to remove contradictory or stale messaging so the docs in `augur` can later be published into `augur-os` through a deploy command, without hand-editing two separate documentation sets.

## Goals

- Make `augur` the single source of truth for project documentation
- Treat the documentation touched in this pass as external-facing by default
- Align top-level docs and deeper docs to the same current-state message
- Add a canonical roadmap surface in `augur`
- Remove stale placeholders, launch contradictions, and messaging drift
- Prepare the docs to be deployable into `augur-os` later

## Non-Goals

- Designing the deploy command in this pass
- Deciding the exact cut line for what will be published into `augur-os`
- Changing code, CI, config, or runtime behavior
- Rewriting every internal markdown artifact if it does not make external claims

## Canonical Rule

For this convergence pass, the docs we touch in `augur` are assumed to be external-facing unless there is a strong reason not to treat them that way.

That means:

- current state must be explicit
- install and support claims must not exceed reality
- platform messaging must be consistent
- roadmap and launch status must be explicit
- placeholders and stale “coming soon” language must be removed or rewritten

## Current State To Reflect

The converged docs should state the following clearly and consistently:

- Augur is in soft launch
- the project is being prepared for broader public release
- native macOS support is implemented
- native Windows architecture is implemented
- Windows validation is still pending before a firmer public support claim
- release planning is active, with roadmap targets visible at top level

## Scope

### In Scope

- top-level markdown docs:
  - `README.md`
  - `CONTRIBUTING.md`
  - `SECURITY.md`
  - `CHANGELOG.md`
  - `ROADMAP.md` (new, if missing)
- the broader `docs/` tree
- public-facing guides and references that make product, install, platform, release, or support claims
- markdown docs that are likely to be part of the future external doc deploy surface

### Out Of Scope

- code
- scripts
- config
- tests
- CI behavior
- runtime systems
- operational implementation changes

## Convergence Priorities

### 1. Top-Level Narrative

The top-level doc set must say one coherent thing about:

- what Augur is
- what state the project is in
- what platforms are supported now versus later
- what the roadmap looks like
- what an interested user should do next

This is the most important layer because it becomes the future public entry surface.

### 2. Platform Messaging

Platform messaging should be consistent across all touched docs:

- native macOS support implemented
- native Windows architecture implemented
- Windows validation pending

No touched doc should imply that Windows is already broadly validated if that is not yet true.

### 3. Install And Readiness Messaging

Docs that mention install, onboarding, dashboard startup, MCP setup, or platform setup must be checked for overclaim.

They do not all need to become minimal.
But they do need to reflect the current state honestly and consistently.

### 4. Roadmap Visibility

`augur` currently lacks a top-level `ROADMAP.md`.
This pass should create a canonical roadmap file in the main repo so roadmap and launch-state messaging no longer live only in the public mirror.

Required roadmap shape:

- current phase: soft launch
- target MVP release timing
- monthly release direction after MVP
- provisional, high-level framing

### 5. Placeholder And Drift Cleanup

Obvious placeholder text and stale launch language should be removed or rewritten.
This includes visible TODO-style prose in external-facing docs and any claims left over from earlier launch assumptions.

## Rollout Strategy

Use a phased documentation-only rollout:

1. top-level doc convergence
2. roadmap creation
3. deeper guide/reference convergence for docs that make external claims
4. contradiction sweep across the full markdown docs surface

This keeps the work bounded and makes it easier to verify that each phase reduces drift.

## Verification

Verification for this pass should be documentation-focused:

- contradiction sweeps with `rg`
- explicit search for install/setup phrases that overclaim
- explicit search for inconsistent platform/support wording
- placeholder scan in touched docs
- manual review of top-level docs as one coherent external narrative

The final result should be a docs set that could be published later without requiring a second editorial pass just to explain the project’s current state.

## Risks

### Over-Public Simplification

If the convergence pass strips too much detail out of `augur`, the canonical docs may become too thin for serious users.

Mitigation:

- preserve useful depth in guides and references
- converge wording, not just shorten everything

### Hidden Contradictions In Deeper Docs

If only top-level docs change, future public publishing will still inherit contradictions from the guides and references.

Mitigation:

- include deeper docs that make external claims
- run a contradiction sweep across markdown, not just the root

### Premature Publishing Assumptions

If docs are rewritten as if public deploy already exists, they can drift again before the deploy command is defined.

Mitigation:

- keep this pass focused on truthfulness and canonicality
- leave deploy mechanics for a later design

## Success Criteria

This convergence pass is successful when:

- `augur` becomes the canonical documentation source
- top-level docs tell one coherent external-facing story
- deeper touched docs do not contradict that story
- a top-level roadmap exists in `augur`
- platform messaging is consistent across touched docs
- the documentation can later be published into `augur-os` with far less editorial work

## Implementation Shape

Implementation should be a docs-only pass in `augur`:

1. converge top-level docs
2. add `ROADMAP.md`
3. align deeper guides/references that make external claims
4. run a markdown contradiction sweep
5. stop once the docs are coherent enough to become the canonical publish source
