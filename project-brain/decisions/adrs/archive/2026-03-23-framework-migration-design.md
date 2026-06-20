# Framework Migration — Domain Features to skills/dashboard/

**Date:** 2026-03-23
**Status:** Draft
**Scope:** Move domain components/lib/hooks from apps/dashboard/ to skills/dashboard/, establish dual-alias import architecture
**Depends on:** ADR-483 (UI Skill Architecture)

## Problem

After ADR-483, custom pages live in `skills/dashboard/pages/` but all components, lib, and hooks remain in `apps/dashboard/`. Domain-specific code (chat, agents, action-bar) is mixed with framework infrastructure (MCP client, auth, plugin system, server utils). There's no architectural boundary between stable infrastructure and volatile features.

Additionally, `apps/dashboard/lib/plugins/` contains ~91 dead mount files from the old plugin system — mostly empty directories and unused Python files.

## Decisions

### 1. Two Source Roots with Stability Boundary

```
@/       → apps/dashboard/*      (framework — stable, changes rarely)
@skill/  → skills/dashboard/*    (features — volatile, changes with every skill)
```

**Dependency rule:** `@/` never imports `@skill/`. `@skill/` can import `@/`. Framework code has zero knowledge of domain features. This is enforced by convention and can be enforced by ESLint.

```typescript
// ✓ Feature importing framework
import { GlassCard } from '@/components/ui/GlassCard';
import { useCachedFetch } from '@/lib/hooks/useCachedFetch';

// ✓ Feature importing feature
import { ChatPanel } from '@skill/components/chat/ChatPanel';

// ✗ FORBIDDEN — framework importing feature
import { Chat } from '@skill/components/chat/Chat';
```

### 2. What Stays in apps/dashboard/ (Framework)

Framework = code that doesn't change when skills are added/removed, AND code that the plugin system (SkillAutoPage, HubTabBar, SectionRenderer) depends on.

**Import-graph validated:** Every module listed below is imported by framework code. Moving any of these would create a forbidden `@/` → `@skill/` dependency.

| Category | Path | Files | Purpose | Imported by (framework) |
|----------|------|-------|---------|------------------------|
| Next.js routes | `app/` | ~50 | Generated catch-all routes, layout, page, API proxy | — |
| UI primitives | `components/ui/` | ~28 | Button, Card, Skeleton, GlassCard, Dialog, etc. | Everything |
| Plugin system | `components/plugin/` | ~42 | SkillAutoPage, HubTabBar, section renderers | app/ routes |
| Framework components | `components/` (top-level) | ~15 | GlobalShell, SidebarNav, ErrorBoundary, providers | app/layout.tsx |
| **Block renderers** | **`components/blocks/`** | **~28** | **BlockRenderer, BlockShell, block type components** | **BlocksSection, DataTableRenderer (plugin/)** |
| Server utils | `lib/server/` | ~21 | cliRunner, pythonRunner, fileOps, commandRunner | API routes |
| MCP client | `lib/mcp/` | ~12 | Connection, diagnostics, useMcpQuery | Everywhere |
| WebMCP | `lib/webmcp/` | ~14 | WebMCP client integration | Plugin system |
| Plugin discovery | `lib/plugin-discovery/` | ~4 | Scanner, paths, types | Mount system |
| Plugin runtime | `lib/plugin-runtime/` | ~11 | Page wrapper, auto-page generation | app/ routes |
| Plugin schema | `lib/plugin-schema/` | ~6 | Config validation (Zod) | Plugin discovery |
| Auth/API | `lib/api/`, `lib/auth/` | ~5 | Session, CSRF, API utilities | API routes |
| Core types/utils | `lib/` (top-level files) | ~24 | shared-types, paths, navigation, cache, dispatch | Everywhere |
| **Block system** | **`lib/blocks/`** | **~7** | **Block types, registry, resolver, useBlockData** | **webmcp, browse, plugin system** |
| **Tab system** | **`lib/tabs/`** | **~6** | **Tab registry, grouping, types** | **HubTabNav, HubLandingPage (plugin/)** |
| **Renderer** | **`lib/renderer/`** | **~6** | **MarkdownRenderer, YAML rendering** | **SectionRenderer (plugin/)** |
| **Mode stores** | **`lib/stores/modeStore`, `airplaneModeStore`** | **~2** | **Dev mode, airplane mode state** | **SkillAutoPage (plugin/)** |
| **Browse** | **`lib/browse/`** | **~4** | **Browse indexing, skill detail** | **webmcp/tools, useSkillDetail** |
| **Chat lib** | **`lib/chat/`** | **~9** | **Quiet filter, context envelope, startup context** | **app/api/cli/ routes** |
| **Help lib** | **`lib/help/`** | **~2** | **stripPII, help utilities** | **app/api/[...proxy]/_helpers.ts** |
| **Templates lib** | **`lib/templates/`** | **~3** | **Template types, formatTemplateLabel** | **HubLandingPage, TemplateRenderer (plugin/)** |
| **StorageSection** | **`components/StorageSection`** | **~1** | **Path config, RAG index card** | **app/settings/tabs/GeneralTab.tsx** |
| **DisabledSkillPage** | **`components/DisabledSkillPage`** | **~1** | **Disabled skill fallback UI** | **app/settings/skills/, app/(views)/browse/** |
| Framework hooks | `hooks/` (framework subset) | ~10 | useCachedFetch, useActionRunner, useSession, useCSRF | SkillAutoPage, API |
| Build system | `scripts/` | ~15 | mount-plugins, generators, build scripts | — |
| Config/static | `config/`, `public/`, `types/` | ~10 | Route registry, static assets, type defs | — |

**Bold rows** = originally classified as domain but reclassified to framework after import-graph analysis. These are consumed by framework code (plugin system, API routes, app routes). Moving them would create forbidden `@/` → `@skill/` dependencies.

**Pre-move extraction:** `components/chat/utils:formatFileSize` is imported by `components/plugin/sections/shared.ts`. Extract this single utility to `lib/utils/` (framework) before moving chat components. The rest of `components/chat/` moves as a feature.

**Total framework: ~355 files**

### 3. What Moves to skills/dashboard/ (Features)

Features = domain-specific code that is ONLY imported by pages or other domain code. **Verified by exhaustive import-graph analysis** — no framework file imports any of these modules.

| Category | From → To | Files | Purpose |
|----------|-----------|-------|---------|
| Chat components | `components/chat/` → `@skill/components/chat/` | ~27 | Chat UI, messages, input (minus `utils` — extracted to framework) |
| Agents | `components/agents/` → `@skill/components/agents/` | ~14 | Agent cards, telemetry |
| Action bar | `components/action-bar/` → `@skill/components/action-bar/` | ~6 | Action buttons, menus |
| Attention | `components/attention/` → `@skill/components/attention/` | ~1 | Attention items |
| Inbox | `components/inbox/` → `@skill/components/inbox/` | ~3 | Inbox components |
| Layout config | `components/layout-config/` → `@skill/components/layout-config/` | ~7 | Sidebar/tab customization |
| Files | `components/files/` → `@skill/components/files/` | ~2 | File editor, tree |
| Domain widgets | `components/` (domain top-level) → `@skill/components/` | ~20 | DashboardWidget, CalendarWidget, SavedInsights, etc. (minus StorageSection, DisabledSkillPage — reclassified framework) |
| Prompts | `lib/prompts/` → `@skill/lib/prompts/` | ~1 | Prompt templates |
| Layout stores | `lib/stores/` (domain subset) → `@skill/lib/stores/` | ~2 | layoutStore, searchStore (NOT modeStore/airplaneModeStore) |
| Domain hooks | `hooks/` (domain subset) → `@skill/hooks/` | ~15 | useCliChat, useAgentHub, useXtermTerminal, useDataBrowser |

**Total features: ~98 files**

**Reclassified to framework (do NOT move):**
- `components/bridge/` (~8) — HubRenderer imports ConnectSourceModal
- `components/remote/` + `lib/remote/` (~11) — Settings route imports provider config
- `components/shared/` (~16) — Browse route imports shared components
- `components/plugin-wizard/` (~3) — app/layout.tsx imports PluginEventNotifier
- `lib/chat/` (~9) — CLI API routes import quiet-filter, context-envelope, startup-context
- `lib/help/` (~2) — API proxy route imports stripPII
- `lib/templates/` (~3) — Plugin system (HubLandingPage, TemplateRenderer) imports template types
- `components/StorageSection` (~1) — Settings route imports usePathConfig, RagIndexCard
- `components/DisabledSkillPage` (~1) — Settings + browse routes import it

### 4. Delete Dead lib/plugins/

`apps/dashboard/lib/plugins/` contains ~91 files of dead plugin mounts. Before deleting, audit live imports:

```bash
grep -r "lib/plugins" apps/dashboard/app/ apps/dashboard/components/ apps/dashboard/lib/ --include="*.ts" --include="*.tsx" | grep -v "node_modules"
```

**Known live imports (must fix before delete):**
- `knowledge/rag-projects.ts` — verify actual importer, convert to MCP call
- `smb-client-template/posts.ts` — verify actual importer, convert to MCP call
- `linkedin-writer/posts.ts` — verify actual importer, convert to MCP call
- `page-builder/` — verify all page-builder lib files are duplicates of `skills/dashboard/lib/` (moved in ADR-483 Task 6). Confirm no active imports point to the `lib/plugins/page-builder/` copy before deleting.

**Action:** Run the grep above. For each live import, convert to MCP proxy call or verify the file exists in its new location. Then delete the entire directory.

### 5. TypeScript Configuration

```jsonc
// apps/dashboard/tsconfig.json
{
  "compilerOptions": {
    "baseUrl": "../..",
    "paths": {
      "@/*": ["apps/dashboard/*"],
      "@skill/*": ["skills/dashboard/*"]
    }
  },
  "include": [
    "../../skills/dashboard/**/*.ts",
    "../../skills/dashboard/**/*.tsx",
    "../../apps/dashboard/**/*.ts",
    "../../apps/dashboard/**/*.tsx",
    ".next/types/**/*.ts",
    ".next/dev/types/**/*.ts"
  ]
}
```

Changes from current:
- Remove `@/pages/*` special alias (subsumed by `@skill/*`)
- Add `@skill/*` → `skills/dashboard/*`
- `@/*` stays as `apps/dashboard/*`

**Note:** This uses the same `baseUrl: "../.."` + Turbopack `root: repoRoot` mechanism already validated by the `@/pages/*` alias in ADR-483. No new Turbopack configuration needed.

### 6. Registry Import Path Update

Mount system's `generate-registry.ts` import path template changes:

```typescript
// FROM (current):
importPath: `@/pages/${toPosixPath(path.join(hubId, entry.slug, "page"))}`,

// TO:
importPath: `@skill/pages/${toPosixPath(path.join(hubId, entry.slug, "page"))}`,
```

**Important:** Steps 5 and 6 must be atomic — update tsconfig AND run `mount-plugins` to regenerate registries in a single commit. Removing `@/pages/*` from tsconfig without regenerating registries breaks the build.

### 7. Import Rewrite Strategy

Moved files that import other moved files need `@/` → `@skill/` rewriting. Files that import framework code keep their `@/` prefix.

**Classification rule:**

Stays `@/` (framework):
- `@/components/ui/*`, `@/components/plugin/*`, `@/components/blocks/*`
- `@/components/GlobalShell`, `SidebarNav`, `ErrorBoundary`, `StorageSection`, `DisabledSkillPage`
- `@/components/bridge/*`, `@/components/remote/*`, `@/components/shared/*`, `@/components/plugin-wizard/*`
- `@/lib/mcp/*`, `lib/server/*`, `lib/plugin-*/*`, `lib/webmcp/*`
- `@/lib/blocks/*`, `lib/tabs/*`, `lib/renderer/*`, `lib/browse/*`
- `@/lib/chat/*`, `lib/help/*`, `lib/templates/*`, `lib/remote/*`
- `@/lib/stores/modeStore`, `lib/stores/airplaneModeStore`
- `@/lib/shared-types`, `lib/paths`, `lib/navigation`, `lib/cache`
- `@/hooks/useCachedFetch`, `useActionRunner`, `useSession`, `useCSRF`

Becomes `@skill/` (domain — only after the file is moved):
- `@/components/chat/*` (minus utils — extracted), `agents/*`, `action-bar/*`
- `@/components/attention/*`, `inbox/*`, `layout-config/*`, `files/*`
- `@/components/DashboardWidget`, `CalendarWidget`, `SavedInsights`, etc. (minus StorageSection, DisabledSkillPage)
- `@/lib/prompts/*`
- `@/lib/stores/layoutStore`, `lib/stores/searchStore`
- `@/hooks/useCliChat`, `useAgentHub`, `useXtermTerminal`, `useDataBrowser`

**Test file imports:** After each category move, also update test imports in `skills/dashboard/pages/**/*.test.tsx` and `apps/dashboard/__tests__/` that reference moved paths.

## Migration Order

1. **Extract `formatFileSize`** — Move `components/chat/utils:formatFileSize` to `lib/utils/` so `plugin/sections/shared.ts` can import from framework without depending on chat. Build. Commit.
2. **Audit and delete dead lib/plugins/** — Grep for ALL live imports, fix each (convert to MCP calls or verify duplicate exists in new location), then delete ~91 files. Build. Commit.
3. **Update tsconfig + registry (atomic)** — Add `@skill/*` alias, remove `@/pages/*`, regenerate registries with `@skill/pages/`, rebuild mount scripts, run mount-plugins. Single commit. Build.
4. **Move domain components batch 1** — Chat components (~27, without utils). Rewrite imports in moved files and their page consumers. Build. Commit.
5. **Move domain components batch 2** — Agents (~14) + action-bar (~6). Rewrite imports. Build. Commit.
6. **Move domain components batch 3** — Attention + inbox + layout-config + files (~13). Rewrite imports. Build. Commit.
7. **Move domain components batch 4** — Domain widgets (~20, excluding StorageSection and DisabledSkillPage). Rewrite imports. Build. Commit.
8. **Move domain lib + stores** — Prompts + domain stores (layoutStore, searchStore) (~3). Rewrite imports. Build. Commit.
9. **Move domain hooks** — Split hooks/ into framework (stays) and domain (~15 moves). Rewrite imports. Build. Commit.
10. **Final verification** — Full build, page count check, spot-check critical pages, run tests.

## Key Constraints

- **Dependency direction enforced:** `@/` never imports `@skill/`. Violation = architecture bug.
- **Import-graph validated boundary:** The framework/features split was derived from the actual import graph, not from intuition. Every module staying in `@/` is imported by at least one framework file.
- **Move categories atomically:** Move all of `chat/` at once, not file-by-file. Rewrite imports immediately in the same commit.
- **Build after each batch:** Each step must leave the build green. Never batch multiple moves without building between them.
- **Atomic tsconfig + registry:** Step 3 (tsconfig alias change + registry regeneration) must be in a single commit. Splitting them breaks the build.
- **Audit before delete:** Never delete `lib/plugins/` without first verifying every live import is resolved.
- **Extract before move:** Extract `formatFileSize` from `chat/utils` to `lib/utils/` BEFORE moving chat components (step 1 before step 4).
- **Test imports too:** After each move, grep test files for stale imports and update them.
- **Test imports too:** After each move, grep test files for stale imports and update them.
