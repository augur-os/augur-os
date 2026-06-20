---
id: ADR-514
title: Vault Cleanup — Phased Reduction from 3,371 to 1,600 Files
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [vault, cleanup, data-hygiene, retention]
related: []
---

# ADR-514: Vault Cleanup — Phased Reduction from 3,371 to 1,600 Files

## Context

The vault at Au-vault/ grew to ~3,371 content files. Many are system-generated ephemeral data, orphaned references (480 files referencing dead `augur-data/` paths), runtime state misplaced in version-controlled storage, duplicated memory entries (67 overlapping), and stale scraped content (174 ephemeral LinkedIn job scrapes).

## Decision

Phased cleanup with 30-day aggressive retention, ordered by risk:

1. **Phase 1 — System artifacts** (zero risk): 62 files — .DS_Store, _index.cache.yaml, seed duplicates
2. **Phase 2 — Dead references** (low risk): 649 files — channels/reviews/expiry-* and attention/expiry-* referencing dead paths
3. **Phase 3 — Runtime state** (low risk): 32 files — Apple _sync.yaml, validator test captures
4. **Phase 4 — Memory dedup** (medium risk): 67 files — keep system/ versions, remove entries/ duplicates
5. **Phase 5 — Ephemeral scrapes** (medium risk): 174 files — career/job-analyzer/jobs/active/
6. **Phase 6 — Attention pending** (higher risk): regenerable expiry items with dashboard impact warning

MCP consumer mapping verified — actively consumed paths preserved, orphaned paths cleaned.

## Consequences

### Positive
- ~1,771 files removed, vault reduced to ~1,600 manageable content files
- Dead references no longer pollute search results
- Runtime state moved to proper platform directories

### Negative
- Attention dashboard temporarily empty until scanner re-populates (Phase 6)
- Notification history cleared (Phase 6)

## References

- Spec: `docs/superpowers/specs/2026-03-24-vault-cleanup-design.md`
- Plan: `docs/superpowers/plans/2026-03-24-vault-cleanup.md`
