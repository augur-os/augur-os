---
title: Dashboard And Browse Surface Governance
summary: Architecture decisions that shape dashboard composition, MCP-facing page
  boundaries, browse UX, and user-visible information architecture.
tags:
- dashboard-and-browse-surface-governance
- documentation-and-repo-maintenance-commands
- operational-audit-and-observability-commands
- plugin-client-and-skill-distribution-governance
- command
- dashboard
- browse
- surface
aliases: []
related:
- '[[documentation-and-repo-maintenance-commands]]'
- '[[operational-audit-and-observability-commands]]'
- '[[plugin-client-and-skill-distribution-governance]]'
created: '2026-04-23T10:46:56Z'
_page_type: concept
_hub: command
_sources:
- adr:adrs/ADR-450-template-driven-dashboard.md
- adr:adrs/ADR-457-dedicated-mcp-tools.md
- adr:adrs/ADR-465-universal-mcp-proxy.md
- adr:adrs/ADR-471-augur-project-framework.md
- adr:adrs/ADR-478-browse-index-freshness.md
- adr:adrs/ADR-484-page-consolidation.md
- adr:adrs/ADR-540-browse-workbench-redesign.md
- adr:adrs/ADR-541-browse-taxonomy-visibility-and-logs.md
_source_fingerprint: 4ae9e2cd66aeaf02a3a56f07a14d6fe2a2c7dc1be23048586a2bb63d19710f81
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:17:12Z'
_cites:
- '[[adr:adrs/ADR-450-template-driven-dashboard.md]]'
- '[[adr:adrs/ADR-457-dedicated-mcp-tools.md]]'
- '[[adr:adrs/ADR-465-universal-mcp-proxy.md]]'
- '[[adr:adrs/ADR-471-augur-project-framework.md]]'
- '[[adr:adrs/ADR-478-browse-index-freshness.md]]'
- '[[adr:adrs/ADR-484-page-consolidation.md]]'
- '[[adr:adrs/ADR-540-browse-workbench-redesign.md]]'
- '[[adr:adrs/ADR-541-browse-taxonomy-visibility-and-logs.md]]'
_mentions:
- '[[concepts/documentation-and-repo-maintenance-commands]]'
- '[[concepts/operational-audit-and-observability-commands]]'
- '[[concepts/plugin-client-and-skill-distribution-governance]]'
_relates_to:
- '[[browse]]'
- '[[command]]'
- '[[dashboard]]'
- '[[documentation-and-repo-maintenance-commands]]'
- '[[operational-audit-and-observability-commands]]'
- '[[plugin-client-and-skill-distribution-governance]]'
- '[[surface]]'
_entity_tier: 3
---

# Dashboard And Browse Surface Governance

## Compiled truth

### Current Thesis

These ADRs govern the user-visible control plane of Augur: how dashboard pages are composed, how MCP tools back them, how browse surfaces reveal information, and how UI structure stays aligned with user mental models instead of implementation leftovers.

### What This Page Knows

The source set spans template-driven dashboard architecture, dedicated MCP tool boundaries, framework structure, browse freshness indicators, page consolidation, browse workbench redesign, taxonomy visibility, client inventory UX, and the tradeoffs around proxy and page-surface composition. The repeated rule is architectural honesty. A page should expose real domain data through the right tool boundary, with information architecture chosen for users rather than for whichever skill or fallback happened to own the data first.

### Key Dimensions

- Browse and page surfaces need dedicated data contracts instead of generic file-tool abuse or hidden fallbacks.
- Dashboard composition should be driven by reusable building blocks and user-facing structure rather than plugin leakage.
- Framework and page-consolidation choices decide whether the UI stays navigable as more skills and surfaces are added.
- Freshness, taxonomy, and inventory visibility are part of product truth, not secondary polish.

### Recent Shifts

- Browse surfaces moved from rough inventory listings toward explicit workbench, taxonomy, freshness, and client-visibility design.
- Dedicated MCP tool architecture made page correctness depend more on exact tool boundaries and less on generic file operations.

### Open Tensions

- A more composable dashboard can drift into abstraction if template flexibility outruns the clarity of the final user experience.
- Richer browse visibility is useful, but every extra inventory axis risks turning the UI back into an implementation map.

### How to Use This

Use this page when the question is about page ownership, browse UX, dashboard composition, MCP-facing route design, or why a user-visible surface should be structured one way and not another. It is the right starting point when the defect feels like a UI issue but the real boundary may live in tool design, page composition, or browse information architecture.

### Open Questions

- Where should dashboard flexibility stop so user-facing navigation does not collapse back into plugin-driven sprawl?
- Which browse and dashboard surfaces still need narrower tool contracts to avoid generic transport layers hiding product defects?

### Source Basis

- `adr:adrs/ADR-450-template-driven-dashboard.md`: The current dashboard architecture couples UI pages to individual skills.
- `adr:adrs/ADR-457-dedicated-mcp-tools.md`: 38 dashboard API routes call generic `file-list`, `file-write`, and `file-read` MCP tools with domain-specific parameters that don't match the tool schemas.
- `adr:adrs/ADR-465-universal-mcp-proxy.md`: The dashboard had 461 API route files.
- `adr:adrs/ADR-471-augur-project-framework.md`: Augur is currently a single hardcoded project ("Augur") with all external paths derived from that name.
- `adr:adrs/ADR-478-browse-index-freshness.md`: The `/browse` page displays data from RAG indexes (`~/Library/Application Support/Augur/rag/{category}/`).
- `adr:adrs/ADR-484-page-consolidation.md`: The dashboard has 58 pages across 6 hubs totaling ~16,659 LOC.
- `adr:adrs/ADR-540-browse-workbench-redesign.md`: The current `/browse` page successfully exposes Augur's breadth, but it behaves more like a long searchable index than a workspace.
- `adr:adrs/ADR-541-browse-taxonomy-visibility-and-logs.md`: The current `/browse` page exposes too many categories in regular mode and mixes together concepts that users experience differently.

### Related Concepts

- [[concepts/documentation-and-repo-maintenance-commands]]
- [[concepts/operational-audit-and-observability-commands]]
- [[concepts/plugin-client-and-skill-distribution-governance]]

## Timeline

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-450-template-driven-dashboard.md
  The current dashboard architecture couples UI pages to individual skills.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-457-dedicated-mcp-tools.md
  38 dashboard API routes call generic `file-list`, `file-write`, and `file-read` MCP tools with domain-specific parameters that don't match the tool schemas.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-465-universal-mcp-proxy.md
  The dashboard had 461 API route files.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-471-augur-project-framework.md
  Augur is currently a single hardcoded project ("Augur") with all external paths derived from that name.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-478-browse-index-freshness.md
  The `/browse` page displays data from RAG indexes (`~/Library/Application Support/Augur/rag/{category}/`).

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-484-page-consolidation.md
  The dashboard has 58 pages across 6 hubs totaling ~16,659 LOC.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-540-browse-workbench-redesign.md
  The current `/browse` page successfully exposes Augur's breadth, but it behaves more like a long searchable index than a workspace.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-541-browse-taxonomy-visibility-and-logs.md
  The current `/browse` page exposes too many categories in regular mode and mixes together concepts that users experience differently.
