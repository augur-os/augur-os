---
status: Implemented
date: 2026-05-03
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-600: Browse Shared Private Overlay

## Context

Browse should make the shared team brain (`shared-vault/`) and the user's private vault feel like one useful second brain without hiding ownership. The first overlay release focuses on vault content (notes, sources, wiki) plus skills because those are the surfaces where the enterprise/private split matters most for daily use.

The overlay must preserve provenance — duplicates between shared and private must remain visible and clearly labeled — and a `Promote` action must let users propose private content for shared inclusion through append-only packets, never by directly editing canonical shared files.

This builds on the shared-vault enterprise overlay foundation (path helpers and promotion packets) and reuses `src.lib.vault_promotion.create_promotion_packet`.

## Decision

Implement the overlay at index time, not in React and not as an ad hoc merge inside `browse-index`. The RAG index remains the backend contract:

- Scanners (`_scanners_structural.py`, `_scanners_knowledge.py`) write distinct pointer files for shared, private, and packet records, stamping `vault_scope`, `vault_root`, `promotion_state`, `source_path`, and `source_root` metadata on every overlay item.
- A new `src/lib/index/_overlay.py` provides shared metadata helpers, scope literals, and collision-safe output paths.
- ID formats: `vault:{scope}:{rel_path}`, `wiki:{scope}:{rel_path}`, `skill:{source_root}:{name}`. Output paths separate scopes (e.g., `rag/vault/{journey}/{scope}/...`).
- `browse-index` accepts an optional `scope` parameter (`shared`, `private`, `packet`) and a new `promote-browse-item` MCP tool delegates to `create_promotion_packet`.
- The dashboard consumes provenance metadata directly: scope-aware IDs, dedupe key includes `vault_scope` and `source_root` so duplicates remain visible, scope filter in the toolbar, `Shared` / `Private` / `Packet` badges on cards, and a `Promote` action only for private notes/sources/wiki/skills with a resolvable source path.
- Default Browse view stays merged. Promotion writes append-only packets under `shared-vault/inbox/promotions/` and never mutates canonical shared content.

## Consequences

### Positive
- Browse feels like one merged brain while keeping ownership visible.
- Provenance is index-time stable — no per-request merging, no React-side guesses.
- Promotion is safe and reviewable: append-only packets, never direct shared writes.
- Future role-aware ranking and maintainer accept/integrate flows can layer on the same metadata.

### Negative
- Skill, wiki, and vault scanners must each be updated; tests must cover three scopes plus packets.
- Dashboard transforms grow a small overlay surface (`apps/dashboard/lib/browse/overlay.ts`).

### Neutral
- The default merged view keeps duplicate items visible — users see two distinct cards for shared and private versions of the same title until a future identity/collapse design lands.

## Alternatives Considered

### Alternative 1: Merge in the dashboard layer (React)
Rejected. Forces every consumer (search, counts, detail panels) to re-implement merging; provenance becomes a UI concern instead of a data contract.

### Alternative 2: Allow direct edits to shared canonical files
Rejected. PR conflict pressure on shared wiki/notes/skills with 40+ engineers is unworkable. Append-only packets keep PRs additive.

### Alternative 3: Hide private duplicates when a shared version exists
Rejected. Hiding origin contradicts the trust model; users must see both.

## References
- Plan: docs/superpowers/plans/2026-05-03-browse-shared-private-overlay.md
- Spec: docs/superpowers/specs/2026-05-03-browse-shared-private-overlay-design.md
- Foundation: docs/superpowers/plans/2026-05-03-shared-vault-enterprise-overlay-foundation.md
