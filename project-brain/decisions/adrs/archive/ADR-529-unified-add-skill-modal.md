---
status: Implemented
date: 2026-04-02
deciders:
  - gsannikov
related:
  - ADR-275
  - ADR-165
  - ADR-489
  - ADR-491
hub: command
tags:
  - browse
  - import
  - skills
  - dashboard
superseded_by: null
---

# ADR-529: Unified Add Skill Modal

## Context

The browse page's "New Skill" button dispatched a generic IDE prompt ("Create a new skill... Ask me what it should do") with no structure, no options, and no connection to the import skill's 13 MCP tools. The import skill could install from URLs, promote client-native skills, import data folders, and import Notion exports — but none of this was discoverable from the dashboard. Users had to know CLI commands (`/skill eject`, `/import`, `/skillstore`) to access these capabilities.

The gap: the most common entry point for adding skills (the browse page button) was disconnected from the most capable skill acquisition infrastructure (the import skill).

## Decision

Replace the "New Skill" button with an "Add Skill" two-phase modal that surfaces all 6 paths to get a skill into Augur.

### Phase 1: Card Grid

Six cards in a 2x3 grid, each with icon, title, description, and an IDE/In-app badge:

| Card | Badge | Behavior |
|------|-------|----------|
| Create from Scratch | IDE | Dispatch prompt to IDE via `useActionRunner` |
| Install from URL | In-app | 3-step sub-flow: input → analysis/review → configure/install |
| Import Data Folder | In-app | Path input → scan → preview → import |
| Import from Notion | In-app | Path input → import |
| Promote Client Skill | In-app | Pick-list from `list-promotable-skills` → promote |
| Browse Skillstore | IDE | Dispatch `/skillstore` prompt to IDE |

### Phase 2: Sub-flows

**Install from URL** is the most complex sub-flow with 3 internal steps:

1. **Input** — URL + optional "What do you need?" intent field
2. **Analysis & Review** — Source banner (author, stars, license, avatar, GitHub link), security review panel (6 categories: prompt injection, shell execution, filesystem access, network calls, obfuscation, permission escalation), overlap detection (tool name + skill name collisions), bundle handling with per-skill checkboxes
3. **Configure & Install** — Hub mapping, skill name overrides, summary, confirm

**Other sub-flows** are simpler: Import Data Folder (scan + preview + import), Import from Notion (path + import), Promote Client Skill (auto-populated pick-list with client badges).

**Shared post-install success screen** with creator attribution and "Star on GitHub" CTA.

### Backend: New MCP Tool

`list-promotable-skills` — scans `~/.claude/skills/`, `~/.codex/prompts/`, `~/.gemini/skills/`, diffs against `skills/`, returns promotable skills with metadata.

### Backend: Extended `install-skill` Dry-Run

The existing dry-run response is extended with:
- Security scan (6 categories via `security_scanner.py`)
- Overlap detection (tool/skill name collisions via `overlap_detector.py`)
- GitHub metadata (author, stars, license, avatar — cached, non-blocking via `asyncio.to_thread`)
- Intent parameter for filtering
- Bundle flag (v1: single skill only)

### Component Architecture

| Component | File | Responsibility |
|-----------|------|---------------|
| `AddSkillModal` | `features/browse/AddSkillModal.tsx` | Modal shell, step state machine |
| `AddSkillCards` | `features/browse/AddSkillCards.tsx` | Phase 1 card grid, IDE dispatch |
| `StepHeader` | `features/browse/StepHeader.tsx` | Shared back-button + title header |
| `InstallFromUrl` | `features/browse/InstallFromUrl.tsx` | 3-step install sub-flow |
| `ImportDataFolder` | `features/browse/ImportDataFolder.tsx` | Data folder import |
| `ImportFromNotion` | `features/browse/ImportFromNotion.tsx` | Notion import |
| `PromoteClientSkill` | `features/browse/PromoteClientSkill.tsx` | Client skill pick-list |
| `InstallSuccess` | `features/browse/InstallSuccess.tsx` | Success screen + star CTA |
| `types.ts` | `features/browse/types.ts` | Shared types (SourceInfo, SecurityCheck, HUB_IDS) |

### Integration Point

`BrowseCategoryActions.tsx` — `handleNew` for the `skills` category opens `AddSkillModal`. All other categories retain their existing behavior.

## Consequences

### Positive

- All 6 skill acquisition paths are discoverable from a single button click
- Security scanning protects users from prompt injection and malicious skills before installation
- Overlap detection prevents accidental tool name collisions
- Creator attribution with star CTA promotes the skill ecosystem
- User intent field enables smarter filtering and hub suggestions
- Structured forms replace free-form IDE prompts for data-driven paths

### Negative

- `InstallFromUrl` is the most complex component in the browse feature (~360 lines)
- Security scanner uses regex heuristics — false positives are possible, especially the base64 pattern
- Bundle detection is v1 (single skill only) — multi-skill bundles need future work
- Semantic overlap detection (embedding-based) deferred to future enhancement

### Neutral

- IDE-dispatch paths (Create from Scratch, Browse Skillstore) retain identical behavior to the previous button
- No changes to browse grid, cards, detail panel, or other category "New" buttons
- No changes to existing import CLI commands

## Alternatives Considered

### Alternative 1: Expanding Cards Modal

Single modal where clicking a card expands it in-place with its form. Rejected: cramped UX for complex sub-flows like Install from URL, which needs full modal width for security review and configure steps.

### Alternative 2: Slide-In Panel

Right-edge panel instead of centered modal. Rejected: conflicts with the existing browse detail panel, introduces a new UI pattern not used elsewhere in the dashboard.

### Alternative 3: Wizard

Multi-step wizard starting with "What do you want to do?". Rejected: branching complexity multiplies with 6 paths, and users can't compare options at a glance.

### Alternative 4: Smart Single Input

One text field auto-detecting intent (URL → install, name → create). Rejected: auto-detection is fragile and hides available options from users who don't know what to type.

## Implementation Order

### Phase 1: Backend (Tasks 1-4)
1. Security scanner module (`security_scanner.py` + tests)
2. Overlap detector module (`overlap_detector.py` + tests)
3. `list-promotable-skills` MCP tool (`promotable.py` + tests + registration)
4. Extend `install-skill` dry-run with security/overlap/GitHub metadata/intent

### Phase 2: Frontend (Tasks 5-11)
5. `InstallSuccess` shared component
6. `AddSkillModal` + `AddSkillCards`
7. `InstallFromUrl` (3-step sub-flow)
8. `ImportDataFolder`
9. `ImportFromNotion`
10. `PromoteClientSkill`
11. Wire into `BrowseCategoryActions.tsx`

### Phase 3: Review & Hardening
12. Code review (reuse, quality, efficiency)
13. Browser verification

## References

- Design spec: `docs/superpowers/specs/2026-04-02-add-skill-modal-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-02-add-skill-modal.md`
- ADR-275: Skill Import/Export Consolidation
- ADR-165: Decentralized Skill Nav Discovery
- ADR-489: One-Click Onboarding with Portable Skills Pack
- ADR-491: Unified Config-Driven Pages

## Implementation Prompt

> Already implemented. See commit history from `6f6da17ce` (design spec) through `27f10f293` (code review fixes).

**Team name**: `adr-529-add-skill-modal`

### Phase 1: Backend
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Security scanner module + tests | `skills/import/augur/lib/security_scanner.py`, `skills/import/augur/tests/test_security_scanner.py` |
| 1.2 | developer | low | Overlap detector module + tests | `skills/import/augur/lib/overlap_detector.py`, `skills/import/augur/tests/test_overlap_detector.py` |
| 1.3 | developer | medium | list-promotable-skills MCP tool | `skills/import/augur/lib/promotable.py`, `skills/import/scripts/mcp/tools_manage.py` |
| 1.4 | developer | medium | Extend install-skill dry-run | `skills/import/scripts/mcp/tools_install.py` |

### Phase 2: Frontend
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | InstallSuccess + shared types | `features/browse/InstallSuccess.tsx`, `features/browse/types.ts` |
| 2.2 | developer | medium | AddSkillModal + AddSkillCards + StepHeader | `features/browse/AddSkillModal.tsx`, `features/browse/AddSkillCards.tsx`, `features/browse/StepHeader.tsx` |
| 2.3 | developer | high | InstallFromUrl 3-step sub-flow | `features/browse/InstallFromUrl.tsx` |
| 2.4 | developer | low | ImportDataFolder + ImportFromNotion | `features/browse/ImportDataFolder.tsx`, `features/browse/ImportFromNotion.tsx` |
| 2.5 | developer | low | PromoteClientSkill | `features/browse/PromoteClientSkill.tsx` |
| 2.6 | developer | low | Wire into BrowseCategoryActions | `components/shared/BrowseCategoryActions.tsx` |

### Completion Criteria
- [x] All phases executed
- [x] All 17 Python tests pass
- [x] TypeScript compiles with zero errors in features/browse/
- [x] Code review completed (reuse, quality, efficiency)
- [x] shadcn Button/Input adopted across all components
- [x] StepHeader extracted, security scanner file-type filtered
- [ ] Browser verification pending
- [x] ADR status updated to Implemented
