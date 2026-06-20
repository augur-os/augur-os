---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- plugin
- lifecycle
- hardening
superseded_by: null
---

# ADR-187: Plugin Lifecycle Hardening

**Date:** 2026-02-28
**Source:** `/learn refactor` analysis (344 learnings, 7-day window)

## Context

The plugin lifecycle subsystem — discovery, mounting, and registry generation — is the third-highest priority infrastructure area from the refactor analysis (115 points, 6 real issues over 7 days). Three scripts collaborate to take plugins from `augur.yaml` to running dashboard tabs:

1. **`mount-plugins.ts`** (305 lines) — symlinks/copies plugin pages into `src/app/`
2. **`generate-tab-registry.ts`** (505 lines) — assembles hub configs from all `augur.yaml` files into TypeScript registry
3. **`generate-registry.py`** (Python) — generates `skill-registry.md` and JSON indexes

These scripts share no validation layer, leading to repeated classes of bugs.

### Structural Weaknesses

### 1. First-Match Hub Ownership (Silent Shadowing)

`generate-tab-registry.ts` line 166 uses `.find()` to determine the "true owner" of a hub:

```typescript
const trueOwner = allConfigs.find(c => c.config.hub && c.config.hub.id === hub.id)
```

If two skills both declare `hub.id: lifestyle` in their `augur.yaml`, the second one is silently ignored. There is no error, warning, or merge strategy — filesystem iteration order determines which skill "owns" the hub.

Similarly, `mount-plugins.ts` `detectHubIdCollisions()` now throws on collision (ADR-177), but the only resolution is to manually disable one skill. No mechanism for "this skill extends that hub" vs. "this skill owns that hub."

### 2. Bundle Discovery Only Finds Hub Owner

The generated registry (`skill-registry.md`, `generated-registry.ts`) stores only the hub-owning skill per hub. Sibling skills in the same bundle that contribute tabs but don't own the hub are invisible to tools that read the registry. This caused the audit bug (2026-02-25) where dashboard hardening scanned only the owner skill, missing 3+ contributing skills per bundle.

### 3. No Schema Validation for augur.yaml Tab Fields

Tab configuration fields (`nav_mode`, `order`, `hub.id`) are read as untyped strings. A typo like `nav_mode: inlin` (missing 'e') silently defaults to inline display (line 169: `nav_mode === 'inline' || !t.nav_mode`). No Zod/Yup schema validates the YAML structure at build time.

### 4. Safety Threshold Too Low

`generate-tab-registry.ts` line 115 sets `MIN_EXPECTED_HUBS = 5` as a sanity check for scan failures. The actual hub count is 17. If scanning breaks and finds exactly 5-16 hubs, the check passes silently, generating an incomplete registry.

### 5. No Registry Generation Rollback

If `generate-tab-registry.ts` validation fails mid-generation (line 97-108), the process exits with an error. But if intermediate files were partially written (e.g., the TypeScript file was opened for writing before validation), the next run sees a corrupt partial file mixed with stale content.

### 6. Worktree-Stale Generated Files

`generated-registry.ts` is gitignored and regenerated at build time. When working in a worktree, the file doesn't exist until `generate-tab-registry` runs. Scripts that import from it at module level crash on worktree checkout. The plugin rebuild route (ADR-177) runs `generate-tab-registry` after `mount-plugins`, but this ordering isn't enforced anywhere.

### Evidence from Daily Logs

| Date | Issue |
|------|-------|
| 2026-02-28 | detectHubIdCollisions() throws by default (was console.warn) with MOUNT_WARN_ONLY=1 escape hatch |
| 2026-02-28 | mount-plugins page file validation added with hard error on missing page files |
| 2026-02-27 | Plugin rebuild route must run generate-tab-registry AFTER mount-plugins |
| 2026-02-26 | Plugin decentralization as Critical Rule #1 — centralized config is tech debt |
| 2026-02-25 | Dashboard audit must scan all skills in a bundle, not just the hub owner |
| 2026-02-22 | bulk_index.py hardcoded to ai/ and dev/ hubs — 15 of 17 hubs never auto-indexed |

## Decision

### Phase 1: augur.yaml Schema Validation (S effort)

Add a Zod schema for the tab-related fields in `augur.yaml` and validate during `generate-tab-registry.ts`:

```typescript
import { z } from "zod";

const TabSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  nav_mode: z.enum(["inline", "nested", "hidden"]).default("inline"),
  order: z.number().int().min(0).max(999).optional(),
  icon: z.string().optional(),
});

const HubContributionSchema = z.object({
  hub: z.object({
    id: z.string().min(1),
    owner: z.boolean().default(false),
  }).optional(),
  pages: z.array(TabSchema).optional(),
});
```

Validation runs at scan time — a malformed `augur.yaml` produces a clear error with file path and field name, not a silent default.

### Phase 2: Explicit Hub Ownership Model (M effort)

Replace implicit first-match ownership with explicit `owner: true` declarations in `augur.yaml`:

```yaml
# In the owning skill's augur.yaml:
contributions:
  hub:
    id: lifestyle
    owner: true    # This skill owns the hub layout
  pages:
    - id: reading
      title: Reading List
```

```yaml
# In a contributing skill's augur.yaml:
contributions:
  hub:
    id: lifestyle
    owner: false   # Extends, does not own
  pages:
    - id: books
      title: Books Catalog
```

`generate-tab-registry.ts` validates:
- Exactly one skill per hub declares `owner: true` (error if 0 or 2+)
- Non-owners can contribute pages but cannot define hub-level config (title, icon, layout)

### Phase 3: Bundle-Aware Registry (S effort)

Extend the generated registry to include all contributing skills per hub, not just the owner:

```typescript
interface HubRegistryEntry {
  id: string;
  owner: string;           // skill that owns the hub
  contributors: string[];  // all skills contributing pages
  tabs: TabConfig[];       // merged from all contributors
}
```

This makes `discover_bundle_skills()` unnecessary — the registry already knows all contributors.

### Phase 4: Raise Safety Threshold + Atomic Writes (S effort)

```typescript
// Derived from actual hub count, not a magic number
const allHubIds = new Set(allConfigs.map(c => c.config.hub?.id).filter(Boolean));
const MIN_EXPECTED_HUBS = Math.max(allHubIds.size - 2, 10);
// Allow 2 hubs to be disabled, but never below 10
```

For atomic writes, generate into a temp file and rename:

```typescript
const tmpPath = registryPath + ".tmp";
await fs.writeFile(tmpPath, generatedContent);
await fs.rename(tmpPath, registryPath);  // atomic on POSIX
```

### Phase 5: Enforced Build Order (S effort)

Create a single `rebuild-plugins.ts` orchestrator that enforces the correct order:

```typescript
async function rebuildPlugins() {
  await mountPlugins();           // 1. symlink pages into src/app/
  await generateTabRegistry();    // 2. assemble hub configs
  await generateSkillRegistry();  // 3. update skill-registry.md (optional)
}
```

The API route `/api/admin/rebuild` calls this orchestrator instead of individual scripts. Worktree setup calls it after checkout.

## Consequences

### Positive

- Schema validation catches augur.yaml typos at build time, not as silent runtime bugs
- Explicit ownership prevents hub shadowing and makes the ownership model visible in config
- Bundle-aware registry eliminates the recurring "audit only found hub owner" bug class
- Atomic writes prevent corrupt partial registries
- Enforced build order prevents the "generate-tab-registry ran before mount-plugins" class

### Negative

- Phase 2 requires adding `owner: true/false` to all existing `augur.yaml` files (~40 skills with hub contributions) — a one-time migration
- Zod dependency added to the build scripts (already available in `src/dashboard/`)

### Neutral

- Dashboard behavior unchanged — the same tabs appear in the same order
- Existing `augur.yaml` files without `owner` field default to `owner: false` during migration (backwards compatible)

## Impact Manifest

```yaml
paths_renamed: []

apis_changed:
  - function: "detectHubIdCollisions()"
    change: "replaced by ownership validation in schema phase"
  - function: "assembleHubs()"
    change: "extended to track contributors array per hub"

files_affected:
  - src/scripts/generate-tab-registry.ts
  - src/scripts/mount-plugins.ts
  - src/scripts/rebuild-plugins.ts  # NEW orchestrator
  - plugins/*/skills/*/augur.yaml   # owner field migration

patterns_deprecated:
  - pattern: ".find() for implicit hub ownership"
    replacement: "explicit owner: true in augur.yaml"
  - pattern: "MIN_EXPECTED_HUBS = 5 magic number"
    replacement: "dynamic threshold derived from scan results"
  - pattern: "separate mount-plugins + generate-tab-registry calls"
    replacement: "rebuild-plugins.ts orchestrator"
```

## References

- ADR-126: Plugin contributions via augur.yaml
- ADR-230: Per-skill .config YAML state
- ADR-163: Config decentralization (centralized files as tech debt)
- ADR-177: Infrastructure reliability refactor (collision detection hardened)
- `/learn refactor` report (2026-02-28): plugin-lifecycle scored #3 priority (115 points, 6 real issues)
