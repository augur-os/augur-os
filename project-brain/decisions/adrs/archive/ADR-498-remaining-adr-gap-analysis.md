---
id: ADR-498
title: Cross-ADR Gap Analysis and Remediation
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [meta, gap-analysis, autoloop, adaptive-engine, migration]
related: [ADR-443, ADR-412, ADR-417, ADR-434]
---

# ADR-498: Cross-ADR Gap Analysis and Remediation

## Context

After restoring 293 ADRs to the vault and reconstructing 7 lost ADRs (436-442), a gap analysis identified 4 priority areas where accepted ADRs had unimplemented requirements: ADR-443 (autoloop safety), ADR-417 (report-only auto-commands), ADR-412 (hotspot system), and ADR-434 (migration verification harnesses).

## Decision

Prioritize and close gaps in order:
1. **ADR-443** — Implement fix classification gate (`classify_fix()`) returning Safe/Structural/Reverting
2. **ADR-417** — Upgrade `auto-markers` (TODO_CLEANUP resolution at d>=1) and `auto-debt-scan` (marker injection at d>=1, extraction at d>=2)
3. **ADR-412 Phase 3** — Build hotspot tracking (`hot_paths`, `hot_patterns`, `dominant_root_cause`)
4. **ADR-434** — Defer to separate plan (largest scope, 7 test categories)

All Priority 1-3 items were completed in the same session. ADR-434 remains for future work.

## Consequences

### Positive
- Auto-loops no longer silently revert intentional architectural changes
- Report-only loops now apply actual code fixes at higher difficulty
- Hotspot data persists between cycles for focused deepening

### Negative
- ADR-434 migration test harnesses still unimplemented (7 categories)

## References

- Plan: `docs/superpowers/plans/2026-03-19-remaining-adr-gaps.md`
