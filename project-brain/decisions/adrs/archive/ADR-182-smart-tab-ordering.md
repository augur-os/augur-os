---
status: Implemented
date: '2026-02-27'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- smart
- tab
- ordering
superseded_by: null
---

# ADR-182: Smart Tab Ordering

## Context

Tab ordering across hubs is inconsistent — some hubs use explicit `order` fields, others rely on YAML declaration order (effectively random). All tabs render in a flat bar regardless of page maturity, leading to underdeveloped pages cluttering navigation alongside production-ready ones. There is no systematic way to score page readiness or separate mature pages from stubs.

## Decision

Introduce a `/ops-tabs` command with a Python-based maturity scoring engine that:

1. **Scores each page 0-100** from 5 weighted code signals: component LOC (25%), API routes (25%), action buttons (15%), data files (15%), manual state label (20%)
2. **Ranks pages per hub** by score descending
3. **Writes computed `order` values** back to each plugin's `augur.yaml` (decentralized persistence)
4. **Splits pages** into top tabs (`order < 900`) and overflow (`order >= 900`) based on configurable `max_tabs` per hub (default 6)
5. **Renders overflow** via a "More" dropdown in `UnifiedHubTabs.tsx`

### Key design decisions

- **Convention `order < 900 / >= 900`** separates top from overflow without a new per-page field
- **Idempotent** — running twice produces same result if code hasn't changed
- **`order_pinned: true`** prevents the command from overwriting manually set order values
- **No runtime tracking** — maturity measured from code structure, not page-view analytics

## Consequences

### Positive

- Consistent tab ordering across all 17 hubs derived from objective code signals
- Stub pages hidden in overflow until mature enough to earn a top tab slot
- Decentralized — scores written to each plugin's augur.yaml, not a central ranking file
- Repeatable via `/ops-tabs` after any code changes

### Negative

- Score weights are heuristic — may need tuning as hub patterns evolve
- Running the command produces augur.yaml diffs that must be committed

### Neutral

- Overview tab always first (implicit `order: 0`)
- `max_tabs` configurable per hub in augur.yaml hub block

## Alternatives Considered

### Manual ordering only

Each developer sets `order` fields by hand. Rejected: doesn't scale to 17 hubs with 50+ pages, subjective, inconsistent.

### Analytics-based ordering

Track page views and rank by traffic. Rejected: requires runtime telemetry infrastructure, privacy concerns, cold-start problem for new pages.

## References

- [Design doc](../plans/2026-02-27-smart-tab-ordering-design.md) — full scoring engine design
- [Implementation plan](../plans/2026-02-27-smart-tab-ordering-plan.md) — 11-task TDD plan

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: generate-tab-registry
      module: src/dashboard/scripts/generate-tab-registry.ts
      breaking: false  # Added overflow partition
  patterns_deprecated:
    - grep: "order:\\s+\\d+"
      replacement: "Computed by /ops-tabs — use order_pinned: true to override"
  files_affected:
    - glob: "plugins/admin/skills/system-cleanup/scripts/tab_scorer.py"
    - glob: "src/dashboard/scripts/generate-tab-registry.ts"
    - glob: "src/dashboard/components/UnifiedHubTabs.tsx"
    - glob: "plugins/*/skills/*/augur.yaml"
```
