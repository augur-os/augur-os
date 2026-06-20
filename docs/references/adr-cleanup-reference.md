# ADR Cleanup — Detailed Phase Reference

This document contains the detailed 3-phase walkthrough for `/adr cleanup`. The summary lives in `skills/adr/SKILL.md`.

## Phase 1: Scan

1. Determine scope: last 30 days (default), `--all`, or `--range`
2. Use `src.lib.adr_utils` helpers to detect:
   - **Duplicate numbers** — `find_duplicate_adrs(decisions_dir)` → multiple files sharing the same ADR-NNN prefix
   - **Gaps in numbering** — `find_gaps(decisions_dir)` → missing numbers in the sequence
   - **Status issues** — `detect_stale_status(adrs, days=60, decisions_dir=decisions_dir)`:
     - Non-canonical status (raw status normalises to a different canonical value)
     - Stale Proposed (status is Proposed but file is older than 60 days)
3. Present a summary table:

```
ADR Cleanup Scan (last 30 days, 25 ADRs)
─────────────────────────────────────────
Issues found: 8

Duplicates (3):
  ADR-221  5 files → should be ADR-221, ADR-223, ADR-224, ADR-225, ADR-226
  ADR-129  2 files → should be ADR-129, ADR-227
  ...

Gaps (2):
  ADR-206, ADR-208  (available for reuse during renumbering)

Status issues (3):
  ADR-192  "In Progress" → should be "Accepted"
  ADR-045  Proposed (90+ days old) → suggest Deprecated?
  ADR-218  Accepted but all files exist → suggest Implemented?
```

4. If `--dry-run`, stop here.

## Phase 2: Plan (Interactive)

For each issue category, ask the user how to proceed:

- **Duplicates**: "Renumber ADR-221 duplicates to ADR-223-226? (keeps oldest file as ADR-221)" — Yes/Skip/Custom
- **Gaps**: "Fill gap ADR-206 during renumbering?" — Yes/No (gaps are cosmetic, not mandatory to fix)
- **Status fixes**: Present each suggestion, let the user approve/reject individually

## Phase 3: Apply

For approved changes:

1. **Renumber** — use `rename_adr(old_path, new_number, decisions_dir)` from `src.lib.adr_utils`. This renames the file, updates the `# ADR-NNN:` title inside the file, and updates `ADR-NNN` cross-references in ALL other ADR files.
2. **Status normalize** — update the `**Status**:` line in the file (same as `set` action).
3. **Regenerate index** — run `python .github/scripts/generate_adr_index.py`
4. **Report** — summary of all changes made:

```
ADR Cleanup Complete
────────────────────
Renamed: 5 files
  ADR-221-b.md → ADR-223-b.md
  ADR-221-c.md → ADR-224-c.md
  ...

Status updated: 2 files
  ADR-192: "In Progress" → "Accepted"
  ADR-045: "Proposed" → "Deprecated"

Cross-references updated: 12 files
Index regenerated: docs/generated/adr-index.md
```

## Validation After Apply

- Grep the ADR directory (`get_documents_dir()/adrs/`) for old ADR numbers to confirm cross-references are updated
- Verify no duplicate numbers remain via `find_duplicate_adrs()`
- Check `docs/generated/adr-index.md` has no duplicates
