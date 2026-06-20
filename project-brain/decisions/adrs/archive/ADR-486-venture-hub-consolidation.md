---
status: Cancelled
date: 2026-03-23
deciders:
- Gur Sannikov
related:
- 469
- 163
- 484
hub: career
tags:
- venture
- hub
- consolidation
- business
- skills
- career
superseded_by: null
---

# ADR-486: Venture Hub Consolidation

## Context

Business capabilities are fragmented across three separate skills: `venture-augur` (a hub with 8 tabs covering Overview/Strategy/Competition/Community/Marketing/Sales/Investors/Social), `business-expert` (a consulting-template agent with commands but no UI), and `contract-reviewer` (an agent that was removed). The `business-expert` commands (TAM analysis, competitor analysis, lead qualification, investor prep, pricing strategy, blue ocean, pipeline, proposals) are inaccessible from the dashboard. There is no unified business intelligence view, no financial tracking, no market analysis, and no outreach/networking capability.

## Decision

Consolidate all business capabilities into a single expanded Venture hub with 15 pages organized into 5 groups. Deprecate `business-expert` and `contract-reviewer` as standalone skills; absorb their capabilities into venture.

### Page structure (15 pages, 5 groups)

| Group | Pages |
|-------|-------|
| Overview | `/venture` (KPIs + alerts), `/venture/analytics`, `/venture/strategy` |
| Market | `/venture/competition`, `/venture/market` (TAM/SAM/SOM), `/venture/positioning` (blue ocean) |
| Growth | `/venture/marketing`, `/venture/content`, `/venture/social`, `/venture/community` |
| Revenue | `/venture/sales`, `/venture/outreach`, `/venture/contracts` |
| Funding | `/venture/investors`, `/venture/financials` |

6 pages are new (Analytics, Market, Positioning, Content, Outreach, Financials). 9 pages are promoted/expanded from existing venture tabs.

### Skill consolidation

`business-expert` commands map to venture pages: `analyze competitors` → Competition, `tam analysis` → Market, `blue ocean` → Positioning, `pipeline` / `qualify` / `proposal` → Sales, `investor prep` → Investors, `pricing strategy` → Strategy, `calculate risk` → Competition.

`contract-reviewer` capabilities (`review contract`, `risk assessment`, `negotiation guide`) → Contracts page.

Both source skills deprecated and archived after capability migration is complete.

### Data structure

New YAML data directories under `plugins/professional/` for each page: `analytics/`, `market/`, `positioning/`, `content/`, `outreach/`, `contracts/`, `financials/`. Existing directories (`competition/`, `sales/`, `investors/`, `marketing/`, `social/`, `community/`, `strategy/`) are retained.

### Implementation phases

1. Data structure — create directories, migrate existing data, define YAML schemas
2. SKILL.md update — merge all capabilities from business-expert
3. Dashboard pages — build placeholder components for 6 new tabs, then implement full UI
4. Actions — migrate business-expert actions, add new per-page actions
5. Cleanup — archive deprecated skills, update navigation and agent-rules references

## Consequences

### Positive
- All business intelligence accessible from one hub with clear navigation groups
- `business-expert` commands discoverable from the dashboard (currently CLI-only)
- Financial tracking, market analysis, outreach, and contracts get dedicated pages
- Single SKILL.md for all business capabilities simplifies agent lookup

### Negative
- 6 new pages require new MCP tools for their data sources — significant backend work
- `business-expert` deprecation means any direct CLI invocations of it stop working after archival (see note on aliases below)
- `plugins/professional/` data directory will grow substantially — needs YAML schemas per new type

### Neutral
- Page count increase (8 → 15) is intentional — one clear question per page over mega-tabs
- Source spec notes to keep business-expert commands as aliases in venture during transition; CLAUDE.md rule 14 (no backward-compat stubs) applies — aliases should have a hard removal date, not persist indefinitely
- Social media integration with external APIs (Buffer, Hootsuite) deferred to future ADR

## Alternatives Considered

### Keep `business-expert` as separate CLI-only skill
Rejected: capabilities remain invisible in the dashboard. The goal is a unified venture workspace, not a split between UI and CLI.

### Expand existing 8-tab venture page with more tabs
Rejected: tabs don't scale past ~8 without UX degradation. ADR-484 decision is zero internal tabs — each concern gets its own page.

### New standalone hub (e.g., `business`)
Rejected: venture already exists with the right scope. Adding a parallel hub creates confusion about which to use.

## References

- Source spec: `docs/guides/venture-hub-design.md`
- ADR-469: Hub Restructuring
- ADR-484: Page Consolidation (no internal tabs; use standalone pages)
- ADR-163: Plugin decentralization

## Impact Manifest

```yaml
skills_deprecated:
  - plugins/consulting/skills/consulting-template/  # business-expert
  - contract-reviewer/  # was already removed

pages_added: 6
  - /venture/analytics
  - /venture/market
  - /venture/positioning
  - /venture/content
  - /venture/outreach
  - /venture/financials

pages_expanded: 9
  - /venture (landing: KPIs + alerts)
  - /venture/strategy
  - /venture/competition
  - /venture/marketing
  - /venture/social
  - /venture/community
  - /venture/sales
  - /venture/contracts
  - /venture/investors

data_dirs_added:
  - plugins/professional/analytics/
  - plugins/professional/market/
  - plugins/professional/positioning/
  - plugins/professional/content/
  - plugins/professional/outreach/
  - plugins/professional/contracts/
  - plugins/professional/financials/
```
