---
status: Implemented
date: 2026-04-03
deciders:
  - gsannikov
related:
  - ADR-514
  - ADR-491
  - ADR-404
hub: null
tags:
  - vault
  - dashboard
  - mcp
superseded_by: null
---

# ADR-531: Vault File Audit and Dashboard Wiring

## Context

ADR-514 reduced the vault from 3,371 to ~1,182 files by removing obvious junk (cache files, dead references, expired operational data). The surviving 1,182 files were assumed to be valuable, but no audit had verified whether each file was:

1. Actually connected to the dashboard (fetched by an MCP tool that a page calls)
2. Runtime/generated state that belonged elsewhere
3. A small fragment worth consolidating
4. Correctly formatted per ADR-404
5. A leftover from the first pass

Additionally, the connectivity audit revealed that only 5 vault directories had dedicated MCP tool wiring to dashboard pages (memory, attention, apple, file-manager, dashboard). The remaining 31 directories were accessible only through the generic browse auto-page — a flat list of 20 files with 200-character previews. High-value skills like career (55 files), venture-augur (46), and growth (29) had no structured dashboard presence.

## Decision

### Phase 1: Vault File Audit

Executed a 5-dimension audit of every vault file using 8 parallel agents, each assigned non-overlapping directory batches. A connectivity map was built first by grepping MCP tool registrations for vault path references, then cross-referencing with dashboard `useMcpQuery` calls.

**Directory-specific disposal rules** governed autonomous decisions:
- ADRs, specs, plans, career data, linkedin posts → always keep
- Channels, attention expiry, daemon operational state → delete or move to runtime
- Skill data with no matching skill → delete (orphaned)
- Ambiguous files → default to keep, tag with `x-status: disconnected`

**Result**: 1,182 → 936 files (20.8% reduction). Cumulative from original: 3,371 → 936 (72%).

| Action | Count |
|--------|-------|
| Format fixed (ADR-404 frontmatter) | 121 |
| Consolidated (small files → topic clusters) | 138 → 9 |
| Moved to runtime | 58 |
| Deleted (duplicates) | 40 |
| Deleted (stale/orphaned) | 28 |
| Relocated (config → skill) | 1 |

### Phase 2: Dashboard Wiring Infrastructure

**Generic vault MCP tools** (new module `src/mcp/augur_mcp/core/vault_ops.py`):
- `vault-file-read` — returns full content with parsed frontmatter, line count, modified date. Path traversal protection.
- `vault-file-write` — creates/updates vault files with YAML frontmatter via `write_frontmatter()`. Creates parent dirs.

**Enhanced `list-skill-vault-notes`** (modified `core/skills.py`):
- 50-file limit (was 20), 3 levels deep (was 2), 500-char previews (was 200)
- Directory grouping: files organized by subdirectory in `groups[]` response
- Type extraction: frontmatter `type` field included per file
- Line count per file
- Backwards compatible: flat `notes[]` array still returned

**Enhanced `VaultNotesBlock`** (modified component):
- Collapsible directory sections with folder icons and file count badges
- Type-aware icons (note, idea, post, config, doc, interview)
- New config props: `directory_filter`, `collapsed`, `sort`
- Search across all groups

### Phase 3: Custom Pages

**YAML pages** (leverage enhanced VaultNotesBlock):
- LinkedIn-writer: posts prominent, context/assets collapsed
- Lifestyle: ideas, recipes, knowledge in separate filtered sections

**TSX pages** (interactive features beyond YAML capability):
- Career Pipeline: stat bar (job counts by status), data table with filters, action buttons
- Career Profile: candidate summary card, tabbed vault browsing, lazy-loaded CV display
- Venture-augur Content: sidebar navigation by 14 subdirs, preview cards, full content expansion, new doc action
- Growth Learning Dashboard: progress cards (courses/knowledge/hardening), guided IDE prompts, activity feed
- Growth Knowledge Browser: grouped file listing, expandable content via vault-file-read, review date badges

## Consequences

### Positive

- Every vault file has been classified and audited — no more unknown content
- 72% total vault reduction from the original 3,371 files improves RAG search quality
- All 31+ skills now get directory-grouped, type-aware vault browsing automatically
- 5 highest-value skills have dedicated interactive dashboard pages
- `vault-file-read` and `vault-file-write` are generic tools — any future skill page can use them
- Per-directory commits in vault repo enable granular rollback

### Negative

- 50-file limit means large categories in some skills may not show all files
- TSX pages reference specific MCP tools — if tool names change, pages break
- Growth skill hub assignment changed from career to brain — may require mount-plugins rebuild

### Neutral

- Connectivity map (at /tmp/vault-cleanup/connectivity-map.json) is ephemeral — regenerate if needed
- The enhanced VaultNotesBlock is backwards compatible — existing consumers unaffected
- YAML pages for linkedin-writer and lifestyle replace the auto-page for those skills

## Alternatives Considered

### Alternative 1: Manual per-file review

Review each of 1,182 files manually without parallel agents. Rejected: would take hours and lack consistency across directories. The 8-agent parallel approach completed in ~7 minutes with per-directory disposal rules ensuring consistent treatment.

### Alternative 2: YAML pages for all 5 skills

Use YAML page configs instead of TSX for career, venture-augur, and growth. Rejected per CLAUDE.md rule 25: career pipeline needs data tables with filters and row actions, venture-augur needs sidebar navigation with content expansion, growth needs guided prompts with IDE dispatch. These interactions exceed YAML block system capability.

### Alternative 3: Upgrade auto-page only (no custom pages)

Only enhance `list-skill-vault-notes` and `VaultNotesBlock` without building custom pages. Rejected: the auto-page upgrade helps all skills but doesn't provide structured browsing (tabs, categories, stat cards) that high-value skills need for usability.

## References

- `docs/superpowers/specs/2026-04-03-vault-file-audit-design.md` — vault audit design spec
- `docs/superpowers/specs/2026-04-03-vault-dashboard-wiring-design.md` — dashboard wiring design spec
- `docs/superpowers/plans/2026-04-03-vault-file-audit.md` — audit execution plan (8 agents)
- `docs/superpowers/plans/2026-04-03-vault-dashboard-wiring-infra.md` — infrastructure plan (Plan A)
- `docs/superpowers/plans/2026-04-03-vault-dashboard-wiring-tsx.md` — TSX pages plan (Plan B)
- `docs/generated/vault-cleanup-report.md` — full audit report with per-directory tables
- ADR-514: Vault Cleanup — Phased Reduction (predecessor)
- ADR-491: Unified Config-Driven Pages (YAML page system)
- ADR-404: Frontmatter format standard

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: Au-vault/config/skill-score-weights.yaml
      to: skills/auto-skill-quality/assets/seeds/skill-score-weights.yaml
  apis_changed:
    - tool: list-skill-vault-notes
      change: Added groups[], stats{} to response (backwards compatible — notes[] preserved)
    - tool: vault-file-read
      change: New tool — reads full vault file content with frontmatter
    - tool: vault-file-write
      change: New tool — creates/updates vault files with frontmatter
  patterns_deprecated: []
  files_affected:
    - src/mcp/augur_mcp/core/vault_ops.py (new)
    - src/mcp/augur_mcp/core/skills.py (modified — list_skill_vault_notes_impl)
    - src/mcp/augur_mcp/core/__init__.py (modified — tool registration)
    - apps/dashboard/components/blocks/types/VaultNotesBlock.tsx (modified)
    - skills/linkedin-writer/augur/pages/overview.yaml (new)
    - skills/lifestyle/augur/pages/overview.yaml (new)
    - skills/career/augur/dashboard/pipeline/page.tsx (new)
    - skills/career/augur/dashboard/profile/page.tsx (new)
    - skills/venture-augur/augur/dashboard/venture-augur/page.tsx (new)
    - skills/growth/augur/dashboard/growth/page.tsx (new)
    - skills/growth/augur/dashboard/knowledge/page.tsx (new)
```
