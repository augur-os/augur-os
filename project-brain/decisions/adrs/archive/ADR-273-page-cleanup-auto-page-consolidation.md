---
status: Implemented
date: '2026-03-12'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- page
- cleanup
- auto
- page
- consolidation
superseded_by: null
---

# ADR-273: Page Cleanup — Auto-Page Consolidation and Stub Removal

**Related ADRs**: ADR-272 (Enhanced Auto-Pages), ADR-406 (Block System UI), ADR-190 (Page Builder)

## Context

ADR-272 introduced `<SkillAutoPage>`, a runtime component that renders rich, data-driven pages for any skill from standard sources (augur.yaml, vault, documents, MCP tools, logs). With this in place, a large number of existing custom skill pages are now redundant:

- **71 stub pages**: Identical 44-line "This is a new skill" placeholder templates auto-generated during skill creation. They show only an AlertCircle icon and getting-started bullet list — strictly less useful than SkillAutoPage.
- **19 auto-wrapper pages**: Thin 5-line redirects or component delegates that add zero content.
- **21 low-quality pages**: Minor customizations (a status card, a simple list, a document panel) that SkillAutoPage already covers or could absorb with small template enhancements.

Separately, the `/help` route serves as a skill directory (browse all 125+ skills, search, view README). This overlaps in spirit with auto-pages but serves a distinct purpose: **discovery** (find skills) vs **dashboard** (monitor/interact with a skill). Rather than merging them, the help route should be renamed to `/skills` to clarify its role as the skill directory and cross-link to each skill's auto-page dashboard.

Total: **~111 pages can be removed**, reducing the codebase from 253 custom skill pages to ~142 genuine custom pages.

## Decision

### D1: Delete Stub Pages (71 pages)

Remove all 44-line placeholder template pages and 13 short delegate stubs. The mount copier (ADR-272) already generates `<SkillAutoPage skillId="X" />` wrappers for skills without custom pages, so deleting stubs causes automatic fallback to the richer auto-page.

### D2: Delete Auto-Wrapper Pages (19 pages)

Remove thin redirect/delegate wrappers that add no content. Skills without a custom page.tsx automatically get a SkillAutoPage wrapper from the copier.

### D3: Absorb Low-Quality Patterns, Then Delete (21 pages)

Before deleting the 21 low-quality pages, analyze their customizations for template absorption:

| Pattern | Count | Absorption |
|---------|-------|------------|
| Document panel editors (YAML/markdown) | 3 | Already covered by DataPreviewSection + VaultNotesSection |
| Simple status cards / info badges | 6 | Already covered by HealthSection + StatsSection |
| Light data lists (PostsList, CompanyList) | 12 | Already covered by DataPreviewSection; skill-specific lists should use customSources in augur.yaml |

If a low-quality page has a small customization not covered by SkillAutoPage's 12 sections, add a `customSources` entry to that skill's augur.yaml so the CustomSourceSection renders it. Then delete the page.

### D4: Rename `/help` → `/skills`

Rename the help route to `/skills` to clarify its purpose as the skill directory. Add a "View Dashboard" link from each skill card in the directory to the skill's auto-page at `/{hub}/{skill}`.

### D5: Update Mount Copier

Update the copier to stop generating stub placeholder pages. Skills without a custom page.tsx should get only the thin `<SkillAutoPage>` wrapper, never the old getting-started template.

## Consequences

### Positive

- **~111 fewer pages** to maintain — significant reduction in dashboard codebase
- **Consistent UX** — every skill gets the same rich auto-page instead of inconsistent stub/low-quality pages
- **Clearer navigation** — `/skills` as directory, `/{hub}/{skill}` as dashboard
- **Faster skill onboarding** — new skills immediately get useful pages without custom TSX

### Negative

- **One-time migration effort** — low-quality pages need augur.yaml `customSources` entries before deletion
- **Breaking change** — `/help` route moves to `/skills`; bookmarks and links break

### Neutral

- 142 genuine custom pages remain untouched
- SkillAutoPage template itself doesn't change (D3 uses existing customSources mechanism)

## Alternatives Considered

### Alternative 1: Merge Help Pages Into Auto-Pages

Rejected. Help serves as a cross-skill directory (search, browse, hub grouping) while auto-pages are single-skill dashboards. Merging would lose the discovery UX or bloat auto-pages with directory features.

### Alternative 2: Keep Low-Quality Pages, Only Delete Stubs

Rejected. The 21 low-quality pages add marginal value over SkillAutoPage and create maintenance burden. Their small customizations are already expressible through augur.yaml `customSources`.

### Alternative 3: Gradual Deprecation With Redirects

Rejected per CLAUDE.md rule 12 ("Break compatibility, do cleanup"). Clean deletion is preferred over redirect shims.

## Testing

### T1: Mount Copier Behavior
- Verify copier generates `<SkillAutoPage>` wrapper (not stub) for skills without custom pages
- Verify copier skips skills that have genuine custom pages

### T2: Auto-Page Renders After Stub Deletion
- Delete a stub page, run copier, verify the skill's route renders SkillAutoPage with real data
- Verify no 404s on previously-stubbed skill routes

### T3: CustomSources Migration
- For each low-quality page migrated to customSources, verify the data appears in CustomSourceSection
- Verify augur.yaml entries are valid and parseable

### T4: Help → Skills Rename
- Verify `/skills` route renders the skill directory
- Verify `/skills/[skill]` renders the skill detail (README)
- Verify "View Dashboard" links navigate to `/{hub}/{skill}`

### T5: Build and Existing Tests
- `npm run build` passes after all deletions
- All pre-existing tests pass (no regressions)
- No broken imports referencing deleted pages

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "app/help/**"
      to: "app/skills/**"
      scope: "apps/dashboard/app/help/**"
  patterns_deprecated:
    - grep: "href.*['\"/]help['\"/]"
      replacement: "href to /skills"
    - grep: "44-line stub placeholder template"
      replacement: "SkillAutoPage wrapper via copier"
  files_affected:
    - glob: "plugins/*/skills/*/augur/dashboard/page.tsx"
```

## Implementation Prompt

**Team name**: `adr-273-page-cleanup`

### Phase 1: Catalog and Classify
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | analyst | low | Generate list of all 71 stub pages (44-line template match) | `plugins/*/skills/*/augur/dashboard/page.tsx` |
| 1.2 | analyst | low | Generate list of all 19 auto-wrapper pages (≤10 lines, redirect/delegate only) | `plugins/*/skills/*/augur/dashboard/page.tsx` |
| 1.3 | analyst | medium | Classify 21 low-quality pages, document each customization that needs augur.yaml migration | `plugins/*/skills/*/augur/dashboard/page.tsx`, `plugins/*/skills/*/augur/augur.yaml` |

### Phase 2: Migrate Low-Quality Customizations
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | implementer | medium | For each low-quality page with non-trivial customization, add `customSources` or `config` entries to the skill's augur.yaml | `plugins/*/skills/*/augur/augur.yaml` |
| 2.2 | validator | low | Verify each migrated augur.yaml parses correctly and CustomSourceSection would render the data | `plugins/*/skills/*/augur/augur.yaml` |

### Phase 3: Delete Pages
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | implementer | low | Delete all 71 stub page.tsx files | `plugins/*/skills/*/augur/dashboard/page.tsx` |
| 3.2 | implementer | low | Delete all 19 auto-wrapper page.tsx files | `plugins/*/skills/*/augur/dashboard/page.tsx` |
| 3.3 | implementer | low | Delete all 21 low-quality page.tsx files (after Phase 2 migration) | `plugins/*/skills/*/augur/dashboard/page.tsx` |
| 3.4 | implementer | low | Run mount copier to regenerate SkillAutoPage wrappers for deleted pages | `apps/dashboard/scripts/mount/copier.ts` |
| 3.5 | validator | low | `npm run build` — verify no broken imports or missing routes | `apps/dashboard/` |

### Phase 4: Rename Help → Skills
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | implementer | medium | Rename `app/help/` → `app/skills/`, update all internal links and navigation references | `apps/dashboard/app/help/**`, `apps/dashboard/components/**` |
| 4.2 | implementer | low | Add "View Dashboard" link to skill cards in the directory | `apps/dashboard/app/skills/page.tsx` |
| 4.3 | implementer | low | Update copier to never generate the old stub template | `apps/dashboard/scripts/mount/copier.ts` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | validator | low | `npm run build` passes |
| V.3 | architect | medium | Spot-check 5 deleted-stub skills render SkillAutoPage correctly |

### Completion Criteria
- [ ] All 111 pages deleted
- [ ] Low-quality customizations migrated to augur.yaml
- [ ] `/skills` route works as skill directory
- [ ] Mount copier generates SkillAutoPage wrappers (not stubs)
- [ ] All tests pass, build passes
- [ ] No orphaned imports referencing deleted pages
