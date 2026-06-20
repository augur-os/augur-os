---
title: Browse Shared Private Overlay Design
date: 2026-05-03
status: approved
scope: design
related:
  - 2026-05-03-shared-vault-enterprise-overlay-design.md
  - 2026-05-03-shared-vault-enterprise-overlay-foundation.md
---

# Browse Shared Private Overlay Design

## Purpose

Browse should make the shared team brain and the user's private vault feel like
one useful second brain without hiding ownership. The first overlay release
focuses on vault content plus skills because those are the surfaces where the
enterprise/private split matters most for daily use.

## Decisions

- Implement the overlay at index time, not in React and not as an ad hoc merge
  inside `browse-index`.
- Include `notes`, `sources`, `wiki`, and `skills` in v1.
- Show shared and private duplicates as separate Browse items.
- Every overlay item exposes provenance metadata: `vault_scope`, `vault_root`,
  `promotion_state`, and source path.
- The default Browse view is merged.
- Browse provides filters for shared, private, and packet items.
- Private overlay items get a `Promote` action that creates an append-only
  promotion packet under `shared-vault/inbox/promotions/`.
- Promotion never edits canonical shared notes, wiki pages, sources, or skills
  directly in v1.

## Scope

In scope:

- Shared/private indexing for vault content roots: `notes`, `sources`, and
  `wiki`.
- Shared/private indexing for canonical skills.
- Browse MCP response metadata for overlay provenance.
- Dashboard badges and filters for shared, private, and packet content.
- A promote action for private notes, sources, wiki pages, and skills.
- Reuse of `src.lib.vault_promotion` for promotion packet creation.

Out of scope:

- Duplicate collapse or private-overrides-shared display merging.
- Maintainer `Accept` or `Integrate` actions.
- Canonical shared wiki rewrites.
- Moving repo-root `skills/` into `shared-vault/skills/`.
- Role-aware ranking.
- Server-hosted enterprise indexing.

## Data Model

Each indexed overlay item adds these metadata fields:

| Field | Meaning |
| --- | --- |
| `vault_scope` | `shared`, `private`, or `packet` |
| `vault_root` | Stable root label such as `shared-vault` or `private-vault` |
| `promotion_state` | `private`, `packet`, `accepted`, or `integrated` |
| `source_path` | Existing source path for the indexed item |
| `source_root` | Existing root classifier when available, extended to distinguish shared/private vault roots |

Shared canonical content normally has `vault_scope: shared` and
`promotion_state: integrated`. Private content has `vault_scope: private` and
`promotion_state: private`. Promotion packet entries have `vault_scope: shared`
and `promotion_state: packet`.

The UI must not infer that two records with the same title are equivalent.
Duplicates stay visible until a later design introduces explicit identity or
collapse rules.

## Indexing

The indexer scans shared and private roots through the path helper layer rather
than hardcoded filesystem paths.

Vault content:

- Scan `shared-vault/notes`, `shared-vault/sources`, and `shared-vault/wiki`.
- Scan the corresponding private vault roots.
- Keep inactive `drafts` and `archive` behavior unchanged.
- Include promotion packets from `shared-vault/inbox/promotions` as packet
  entries so reviewers can see pending shared contributions in Browse.

Skills:

- Continue scanning current repo-root skills during the transition.
- Add `shared-vault/skills` and private vault `skills` as explicit sources.
- Preserve current skill discovery metadata such as client sources and
  ownership.
- Mark shared-vault skills as shared/team-visible and private-vault skills as
  private/user-owned.

Index output should remain normal RAG pointer files so `browse-index`, search,
counts, and detail panels keep one backend contract.

## Browse API

`browse-index` should continue to return one item list per category. It should
add or preserve overlay metadata from index entries and expose enough data for
the dashboard to render:

- provenance badges,
- scope filters,
- promotion action availability,
- original source path or packet path.

Filtering should be available through current metadata/search mechanisms first.
If the existing API cannot express scope filters cleanly, add a narrow optional
parameter such as `scope=shared|private|packet` to the Browse MCP tool and keep
the default merged behavior.

## Dashboard Behavior

The default view stays merged. Cards, table rows, and detail panels show badges:

- `Shared` for shared canonical content,
- `Private` for private vault content,
- `Packet` for promotion packets.

The UI should also expose a compact scope filter alongside existing category
and search controls. It should not hide duplicate shared/private records. A
private item and a shared item with the same title should be visually distinct
through badges and source metadata.

The `Promote` action appears only when:

- the item has `vault_scope: private`,
- the item category is `notes`, `sources`, `wiki`, or `skills`,
- the item has a resolvable source path.

The action should not appear for shared canonical items, packet entries,
archive/draft items, or dev/runtime categories.

## Promote Action

The action creates a promotion packet by calling a backend tool or CLI wrapper
that delegates to `src.lib.vault_promotion.create_promotion_packet`.

Packet request defaults:

- `topic`: item title,
- `contributor`: local configured user when available, otherwise a stable local
  account label,
- `synthesis`: item description plus a short source reference,
- `source_paths`: the selected private source path,
- `roles` and `domains`: copied from item metadata when present,
- `sensitivity`: `internal`.

The action returns the created packet path and refreshes Browse or shows a
success state. It must not write directly to shared canonical folders.

## Error Handling

- Missing shared-vault roots produce zero shared items, not a dashboard failure.
- Missing private vault roots produce zero private items.
- Missing source paths disable `Promote` for that item.
- Packet creation errors should surface the backend error in the action result
  and leave the selected source unchanged.
- Indexing should continue when one root is malformed; the result should include
  warnings where the current indexer already supports them.

## Testing

Focused tests should cover:

- shared/private vault content is indexed with correct provenance metadata,
- promotion packets are indexed as packet entries,
- shared and private duplicates are returned as separate items,
- skills from repo root, shared-vault, and private vault keep distinct
  provenance,
- `browse-index` preserves scope metadata and filters by scope when the filter
  is introduced,
- dashboard transforms render badges and expose `Promote` only for eligible
  private items,
- the promote action creates a packet through the existing packet writer.

Browser verification is required if the implementation touches dashboard UI or
generated dashboard registries.

## Rollout

1. Extend indexer metadata for shared/private vault content.
2. Add shared/private skills provenance.
3. Add Browse API filtering and action metadata.
4. Add dashboard badges, filters, and `Promote` action wiring.
5. Verify with focused Python and dashboard tests, then real browser loading for
   Browse.

This keeps the first release useful and reviewable while preserving the larger
shared-vault migration for later plans.
