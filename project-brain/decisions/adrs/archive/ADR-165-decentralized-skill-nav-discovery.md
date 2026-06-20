---
status: Implemented
date: '2026-02-26'
deciders:
- Gur Sannikov
related:
- ADR-163 (config decentralization)
- ADR-126 (plugin structure)
- ADR-230 (plugin enablement)
- ADR-130 (action discovery)
hub: null
tags:
- decentralized
- skill
- navigation
- discovery
superseded_by: null
---

# ADR-165: Decentralized Skill Navigation Discovery

---

## Context

### The problem

The dashboard sidebar shows an "EXTENSIONS" section with stale entries like "advisor" and "ai-bridge" that shouldn't be there:

- **advisor** declares `nav_mode: hidden` in its augur.yaml — but `DynamicSkillsNav` ignores this field
- **ai-bridge** is a primary hub skill (`contributes_to: ai`) that already has a full sidebar entry under the AI hub — it shouldn't also appear as a standalone extension

This is the visible symptom of a deeper structural problem: **two parallel navigation systems that don't share data**.

### Two disconnected nav pipelines

| Pipeline | Source | Renderer | Data-driven? |
|----------|--------|----------|-------------|
| **Hub nav** (SidebarNav) | `augur.yaml` → `generate-tab-registry.ts` → `generated-registry.ts` | `SidebarNav.tsx` | Yes |
| **Skill nav** (DynamicSkillsNav) | CLI `augur list -j` → `/api/registry` | `DynamicSkillsNav.tsx` | No — uses hardcoded EXCLUDED set (71 items) and CATEGORY_MAP (14 items) |

The hub nav pipeline works correctly — plugins declare `hub.category`, `nav_label`, `nav_hidden` in augur.yaml, and the build-time generator assembles the sidebar. But `DynamicSkillsNav` bypasses all of it and reimplements categorization with brittle hardcoded maps.

### What goes wrong

1. **New skills appear as "Extensions"** — Any skill not in EXCLUDED or CATEGORY_MAP falls through to the Extensions bucket. Adding a new plugin requires remembering to also edit DynamicSkillsNav.tsx.
2. **Plugin metadata is ignored** — `advisor/augur.yaml` declares `nav_mode: hidden`, `executor/augur.yaml` declares `nav_hidden: true`, but DynamicSkillsNav never reads these fields.
3. **Hub-owning skills leak into extensions** — `ai-bridge` contributes to the AI hub and already has a full sidebar section, but also shows up in Extensions because DynamicSkillsNav doesn't check `contributes_to`.
4. **Runtime CLI dependency** — `/api/registry` calls `augur list -j` (CLI subprocess) on every request (with 5-min cache). The same data is available at build time from augur.yaml files.
5. **131 hardcoded entries** — 71 EXCLUDED + 14 CATEGORY_MAP entries that must be manually maintained. Every new skill is a potential nav bug.

### What plugins already declare

The metadata to solve this already exists in augur.yaml:

```yaml
# plugins/dev/skills/advisor/augur.yaml
skill: advisor
contributes_to: dev        # ← hub membership (should suppress standalone nav)
nav_mode: hidden           # ← explicit visibility control

# plugins/orchestration/skills/executor/augur.yaml
nav_hidden: true           # ← alternate visibility control

# plugins/ai/skills/ai_bridge/augur.yaml
skill: ai_bridge
contributes_to: ai         # ← hub-owning skill
hub:
  id: ai
  category: ai             # ← category for sidebar grouping
```

Three fields cover all navigation decisions:
- `contributes_to` → skill belongs to a hub (suppress standalone entry)
- `nav_mode: hidden` / `nav_hidden: true` → explicitly hidden
- `hub.category` → sidebar section categorization (for hub-owning skills)

## Decision

### 1. Add `nav` section to augur.yaml schema (plugin-side)

Skills that want standalone sidebar presence declare it explicitly:

```yaml
# augur.yaml v3.0 — nav section (optional)
nav:
  visible: true              # default: false for contributing skills, true for standalone
  category: Tools            # Tools | Integrations | System (default: inferred from hub.category)
  label: "Custom Label"      # override display name (default: skill display_name)
  icon: Wrench               # Lucide icon name (default: Package)
  route: /custom/path        # override route (default: /skills/{slug})
```

**Visibility rules** (no hardcoded lists):
1. If `nav.visible` is explicitly set → use it
2. If `contributes_to` is set and skill has a `hub:` block (primary hub skill) → hidden from extensions (already in hub nav)
3. If `contributes_to` is set without `hub:` block (contributing skill) → hidden (sub-skill of a hub)
4. If `nav_mode: hidden` or `nav_hidden: true` → hidden (backward compat)
5. Otherwise → visible in Extensions as fallback

### 2. Build-time assembly replaces runtime CLI call

Add a `skill-nav` section to the existing `generate-tab-registry.ts` build step:

```typescript
// generate-tab-registry.ts addition
interface SkillNavItem {
  slug: string;
  label: string;
  icon: string;
  category: string;
  route: string;
}

function assembleSkillNav(augurYamls: AugurYaml[]): SkillNavItem[] {
  return augurYamls
    .filter(y => resolveVisibility(y))  // apply rules 1-5 above
    .map(y => ({
      slug: y.skill,
      label: y.nav?.label ?? y.skill,
      icon: y.nav?.icon ?? 'Package',
      category: y.nav?.category ?? 'Extensions',
      route: y.nav?.route ?? `/skills/${y.skill}`,
    }));
}
```

Output: `src/dashboard/lib/tabs/generated-skill-nav.ts` — a static TypeScript array, zero runtime cost.

### 3. DynamicSkillsNav reads generated data, not CLI

Replace the entire fetch-and-filter flow:

```typescript
// Before: 71 EXCLUDED entries, 14 CATEGORY_MAP entries, runtime CLI call
const res = await fetch('/api/registry');
// ... hardcoded filtering ...

// After: import static generated data
import { skillNavItems } from '@/lib/tabs/generated-skill-nav';
// Zero filtering needed — build step already applied visibility rules
```

Delete: `EXCLUDED` set, `CATEGORY_MAP`, runtime `/api/registry` fetch from DynamicSkillsNav.

### 4. `/api/registry` cleaned up

The `/api/registry` route still serves other consumers (buttons, shortcuts, chains). But the skills list for nav purposes moves to build-time. The registry route keeps serving:
- Action buttons (already data-driven via `loadAllActions()`)
- Shortcuts (config-driven)
- Skills list for non-nav consumers (search, context injection)

Skills returned by `/api/registry` gain nav metadata from augur.yaml so any future consumer can also use it:

```typescript
// Each skill in registry response gains:
{
  name: "advisor",
  hub: "dev",
  nav: { visible: false, reason: "nav_mode:hidden" }  // from augur.yaml
}
```

## Consequences

### Positive
- **Zero hardcoded nav lists** — EXCLUDED (71 items) and CATEGORY_MAP (14 items) deleted entirely
- **Plugin self-containment** — nav visibility is a plugin decision, declared in augur.yaml alongside everything else
- **No runtime CLI call for nav** — build-time assembly, zero latency, no subprocess, no cache staleness
- **Single source of truth** — augur.yaml `nav:` section drives both hub nav and skill nav
- **New skills Just Work** — add a plugin with augur.yaml, run build, nav updates automatically

### Negative
- **Build step required** — changing nav requires `npm run generate-tabs` (already required for hub changes)
- **Schema addition** — augur.yaml gets a `nav:` section (optional, backward-compatible)

### Migration
1. Add `nav:` sections to the ~5 skills that currently appear in Extensions or need explicit visibility
2. Normalize `nav_mode: hidden` and `nav_hidden: true` to `nav.visible: false` across existing augur.yaml files
3. Update `generate-tab-registry.ts` to emit `generated-skill-nav.ts`
4. Rewrite `DynamicSkillsNav.tsx` to import generated data
5. Remove EXCLUDED/CATEGORY_MAP from DynamicSkillsNav.tsx
6. Update `/api/registry` to include nav metadata in skill entries

## Impact Manifest

```yaml
files_affected:
  - src/dashboard/components/DynamicSkillsNav.tsx        # rewrite: remove hardcoded maps
  - src/dashboard/scripts/mount/generate-tab-registry.ts # extend: add skill-nav assembly
  - src/dashboard/lib/tabs/generated-skill-nav.ts        # new: generated skill nav items
  - src/dashboard/app/api/registry/route.ts              # update: add nav metadata to skills
  - plugins/*/skills/*/augur.yaml                        # update: add nav: section where needed

patterns_deprecated:
  - hardcoded EXCLUDED set in DynamicSkillsNav.tsx
  - hardcoded CATEGORY_MAP in DynamicSkillsNav.tsx
  - runtime CLI fetch for sidebar nav data

apis_changed:
  - /api/registry: skills[] gains nav metadata field

paths_renamed: []
```
