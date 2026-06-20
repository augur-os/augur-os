---
status: Implemented
date: '2026-04-20'
deciders:
- Gur Sannikov
related:
- ADR-172
- ADR-404
- ADR-478
- ADR-524
- ADR-540
- ADR-541
hub: brain
tags:
- browse
- skills
- dashboard
- client-inventory
- ux
superseded_by: null
implemented_date: '2026-04-19'
implementation_commits:
- 2e0860d69f
- a9e13c573c
- 50a0fa941c
- 22184f1c16
- 9d990e0f01
- e8f6693e16
- 64d89236b7
---

# ADR-554: Browse Skills Tab UX And Client Inventory

## Context

The Browse page already had a shared shell for indexed categories, but the Skills category was not useful enough for first-run skill inventory work. It treated skills like generic browse records and did not clearly show where a skill came from, which client exposed it, whether it was Augur-owned or external, or what the next useful action should be.

The underlying data also needed to preserve multi-client discovery metadata. Installed Claude, Codex, Gemini, and other client skill surfaces had to remain visible as real skill inventory without turning generated client wrappers into dynamic MCP skill registrations.

## Decision

Keep the existing Browse page and make the Skills category richer inside that shared shell. Do not add a separate Skills page or bypass the `browse-index` MCP data flow.

The implementation adds a skill-specific Browse card and pure skill UX helpers that activate only for `category === "skills"`. The card splits tags into identity metadata and operational state, selects one safe primary action, and keeps secondary or destructive operations in overflow/context actions. The Skills view also includes an inventory summary and client filtering so users can compare Augur, Claude, Codex, Gemini, and external skill sources.

The data path remains:

```text
skill discovery -> RAG skills index -> browse-index(category=skills) -> dashboard transforms -> Browse Skills UI
```

Client-origin metadata is preserved through discovery, RAG indexing, MCP browse shaping, dashboard transforms, filtering, and rendering. Unknown metadata is omitted rather than rendered as placeholder tags.

## Consequences

Positive:

- Browse > Skills now answers what was found, where it came from, and what the user can do next.
- External and client-discovered skills remain visible in the inventory.
- Skills-specific UI does not leak into non-skill Browse categories.
- Search and filtering can use client source metadata instead of only names and descriptions.

Negative:

- Browse has a small amount of category-specific rendering logic for skills.
- Skill card behavior now depends on normalized metadata quality from discovery and indexing.

Neutral:

- Generated local client wrappers remain real installed client skill surfaces, but they are not fed back into MCP dynamic registration.
- Missing optional metadata causes a quieter card, not synthetic labels.

## Implementation Evidence

Key implementation files:

- `src/plugins/skill_discovery.py`
- `skills/rag/scripts/_scanners_knowledge.py`
- `src/mcp/augur_mcp/infrastructure/browse/index.py`
- `apps/dashboard/lib/browse/transforms.ts`
- `apps/dashboard/lib/browse/skill-card-ux.ts`
- `apps/dashboard/components/shared/SkillBrowseCard.tsx`
- `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`
- `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- `apps/dashboard/components/shared/BrowseCategoryActions.tsx`

Representative tests:

- `tests/unit/test_skill_discovery_external_inventory.py`
- `tests/unit/test_browse_skill_inventory.py`
- `tests/dashboard/lib/browse/skill-card-ux.test.ts`
- `tests/dashboard/components/shared/SkillBrowseCard.test.tsx`
- `tests/dashboard/browse/BrowseContentGridSkills.test.tsx`
- `tests/dashboard/browse/BrowseCategoryActions.test.tsx`

## Alternatives Considered

### Build A Separate Skills Page

Rejected. The shared Browse shell already owned category search, filters, freshness, and detail navigation. A separate page would duplicate behavior and split inventory discovery.

### Render All Skill Metadata As Generic Tags

Rejected. Generic tags mixed identity, client source, quality, setup, and capability state into one unreadable cluster. Two tag zones make the card easier to scan.

### Treat Generated Client Wrappers As MCP Dynamic Skills

Rejected. Client wrappers are installed client surfaces and should appear in Browse inventory, but feeding them back into MCP dynamic registration creates command collisions and feedback loops.

## References

Absorbed transient artifacts:

- `docs/superpowers/specs/2026-04-19-browse-skills-tab-ux-design.md`
- `docs/superpowers/plans/2026-04-19-browse-skills-tab-ux.md`

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - src/mcp/augur_mcp/infrastructure/browse/index.py: skills entries preserve client_sources and skill_clients
  - apps/dashboard/app/(views)/browse/useBrowseState.ts: skills filters include client metadata
patterns_deprecated:
  - skills-as-generic-browse-cards-only
files_affected:
  - src/plugins/skill_discovery.py
  - skills/rag/scripts/_scanners_knowledge.py
  - src/mcp/augur_mcp/infrastructure/browse/index.py
  - apps/dashboard/lib/browse/transforms.ts
  - apps/dashboard/lib/browse/skill-card-ux.ts
  - apps/dashboard/components/shared/SkillBrowseCard.tsx
  - apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx
  - apps/dashboard/app/(views)/browse/useBrowseState.ts
  - apps/dashboard/components/shared/BrowseCategoryActions.tsx
```
