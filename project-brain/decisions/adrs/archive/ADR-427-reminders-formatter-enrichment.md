---
status: Implemented
date: 2026-03-16
deciders:
  - Gur Sannikov
related:
  - ADR-421
hub: productivity
tags:
  - apple
  - reminders
  - sync
  - formatter
superseded_by: null
---

# ADR-427: Reminders Formatter Enrichment

## Context

The Apple Reminders sync formatter strips useful data: due date time is actively discarded (`split("T")[0]`), `completionDate` is not pulled on remote-only items, there's no way to inspect raw remindctl JSON for debug/audit, and no extensibility path for future fields.

## Decision

### Two-Tier Field Architecture

- **Tier 1 (structured):** Explicit fields on `SyncItem` with types, merge logic via `_FIELD_MAP`, and conflict detection
- **Tier 2 (pass-through):** `extras: dict` on `SyncItem` for vault markdown fields not explicitly modeled. Round-trips through formatter but doesn't participate in merge or conflict detection.

### Key Changes

1. **`due` preserves full ISO timestamp** — no more `split("T")[0]` stripping
2. **Vault format splits into `due` + `due_time`** — human-readable, auto-recombined by parser
3. **`completionDate` pulled** on remote-only items and during merge (read-only from remote)
4. **Raw payload** dumped to `$AUGUR_STATE/sync/reminders/<list-slug>/payloads.json` for debug/audit
5. **`extras` dict** captures unknown vault metadata keys, survives merge cycles

### Migration

First sync after upgrade triggers one-time pull of time components (remote full ISO != snapshot date-only). Correct and expected — no data loss.

## Consequences

### Positive

- Users see due time (not just date) in vault files
- Extensible — future fields auto-round-trip via extras
- Debug capability via raw payload inspection

### Negative

- One-time migration diff on first sync (all items with due dates show as changed)

### Neutral

- `_FIELD_MAP` and snapshot structure unchanged

## References

- Design doc: `docs/superpowers/specs/2026-03-16-reminders-formatter-enrichment-design.md`
- ADR-421: Apple Reminders Bidirectional Sync
