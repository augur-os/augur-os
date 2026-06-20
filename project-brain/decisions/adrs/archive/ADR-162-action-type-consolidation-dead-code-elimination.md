---
status: Implemented
date: '2026-02-26'
deciders:
- Project team
related:
- ADR-130 (action discovery v2)
- ADR-160 (oneshot agent bubbles)
- ADR-161 (context injection)
hub: null
tags:
- action
- type
- consolidation
- dead
- code
superseded_by: null
---

# ADR-162: Action Type Consolidation and Dead Code Elimination

---

## Context

Post ADR-160 implementation revealed five systemic patterns that create compounding technical debt. Each pattern is individually minor but together they cause cascading breakage whenever a new dispatch mode, page route, or action is added.

### Root Cause 1: DispatchMode Type Duplication

The canonical `DispatchMode` type lives in `src/dashboard/lib/actions/types.ts:10`:
```typescript
export type DispatchMode = 'fire' | 'oneshot' | 'chat' | 'ide' | 'modal';
```

But 15+ plugin TSX files define their own inline union:
```typescript
const handleAction = async (id: string, label: string, dispatch: 'fire' | 'ide' | 'modal') => { ... }
```

When `oneshot` was added (ADR-160), every inline union needed manual updating. Two build failures were caught during the current cleanup; more may lurk in untested paths.

Additional duplicate definitions:
- `src/dashboard/lib/plugin-schema/types.ts:440` — `'fire' | 'oneshot' | 'chat' | 'ide' | 'modal'`
- `src/dashboard/lib/prompt-adapter.ts:10` — `DispatchTarget` adds `'cowork'`
- `src/dashboard/components/DetailPanel.tsx:36` — missing `'chat'` and `'ide'`

### Root Cause 2: Inline ActionDef Construction

15+ files construct `ActionDef`-like objects by hand:
```typescript
const RECIPE_ACTIONS = [
  { id: 'find-similar', label: 'Find Similar', icon: Search, dispatch: 'oneshot' as const },
  // ... duplicating what the YAML already defines
];
```

Then call `useActionRunner().runAction()` with a partial object, hardcoding `page`, `description`, and `dispatch` — duplicating the source-of-truth YAML. When YAML changes, TSX doesn't follow.

### Root Cause 3: Zero Build-Time Config Validation

Six config YAML files in `config/dashboard/` reference skills, pages, tools, and list IDs with no validation:
- `list_shortcuts.yaml` — 100% dead references (all list IDs fail to resolve)
- `mcp_tool_groups.yaml` — 30 skill references, unchecked
- `tool_display_names.yaml` — 65 tool name references, unchecked
- `path_aliases.yaml` — maps to legacy `vertical-work`/`vertical-life` pages that don't exist

### Root Cause 4: Dead Code Accumulation

No tooling detects unused modules:
- `src/dashboard/lib/services/cortex-graph.ts` — 0 imports
- `src/dashboard/lib/services/privacy.ts` — 0 imports
- `config/dashboard/list_shortcuts.yaml` — all entries dead
- `config/dashboard/path_aliases.yaml` — references dead pages

### Root Cause 5: handleAction Pattern Fragmentation

The same 5-line handler is copy-pasted across 15+ plugin files with 3 different signatures:
1. `(actionId: string, label: string, dispatch: 'fire' | 'oneshot' | 'ide' | 'modal') => ...`
2. `(action: ActionItem) => ...`
3. `(actionId: string, label: string, description: string) => ...`

All do the same thing: construct a partial `ActionDef` and call `runAction()`. Each site hardcodes its own `page:` and `description:` values.

---

## Decision

### 1. Import Canonical DispatchMode Everywhere

Replace all inline dispatch union types with the canonical import:

```typescript
import type { DispatchMode } from '@/lib/actions/types';

const handleAction = async (id: string, label: string, dispatch: DispatchMode) => { ... }
```

Remove duplicate definitions in `plugin-schema/types.ts` and `DetailPanel.tsx`. Keep `DispatchTarget` in `prompt-adapter.ts` as it genuinely extends the base type with `'cowork'`.

### 2. Create useActionDispatch Hook

Create a thin wrapper hook that eliminates inline `ActionDef` construction:

```typescript
// src/dashboard/hooks/useActionDispatch.ts
import { useActionRunner } from './useActionRunner';
import type { DispatchMode } from '@/lib/actions/types';

export function useActionDispatch(page?: string) {
  const { runAction, ...rest } = useActionRunner();
  const currentPage = page ?? (typeof window !== 'undefined' ? window.location.pathname : '/');

  const dispatch = (actionId: string, label: string, mode: DispatchMode) => {
    runAction({
      id: actionId,
      label,
      description: label,
      dispatch: mode,
      page: currentPage,
    });
  };

  return { dispatch, ...rest };
}
```

Plugin files change from:
```typescript
const { runAction, isExecuting } = useActionRunner();
const handleAction = async (id, label, dispatch) => {
  await runAction({ id, label, description: `Running ${label}`, page: '/career/hardening', dispatch });
};
```
To:
```typescript
const { dispatch, isExecuting } = useActionDispatch();
// onClick={() => dispatch('harden-knowledge', 'Harden Knowledge', 'oneshot')}
```

### 3. Add Config YAML Validation to plugin-lint

Extend `plugin-lint.py` to validate `config/dashboard/` YAML references:
- Skill IDs in `mcp_tool_groups.yaml` must match discovered skills
- Page paths must match dashboard routes
- Dead files (`list_shortcuts.yaml`, `path_aliases.yaml`) flagged for removal

### 4. Delete Confirmed Dead Code

Remove files with zero imports and no runtime consumers:
- `src/dashboard/lib/services/cortex-graph.ts`
- `src/dashboard/lib/services/privacy.ts`
- `config/dashboard/list_shortcuts.yaml`
- `config/dashboard/path_aliases.yaml`

### 5. Standardize handleAction via useActionDispatch

Migrate all 15+ plugin files from bespoke `handleAction` functions to the shared `useActionDispatch` hook. The hook:
- Derives `page` from `window.location.pathname` (no hardcoding)
- Uses canonical `DispatchMode` type (no inline unions)
- Provides a 3-argument `dispatch(id, label, mode)` function (no object construction)

---

## Consequences

### Positive
- **Type safety**: Adding a new dispatch mode requires changing 1 file, not 15+
- **DRY**: Action dispatch is a shared hook, not copy-pasted boilerplate
- **Build-time detection**: Stale config references caught by CI, not by users clicking broken buttons
- **Smaller bundle**: Dead services removed (~800 lines)
- **Onboarding**: New plugin authors use `useActionDispatch` instead of reverse-engineering the pattern

### Negative
- **Migration churn**: 15+ plugin files touched for hook migration
- **Config validation maintenance**: New config formats need validator updates

### Neutral
- `useActionRunner` remains as the lower-level hook for advanced use cases (custom descriptions, prompt overrides)
- Existing action YAMLs unchanged — this ADR targets TypeScript consumption, not YAML structure

---

## Alternatives Considered

### 1. Central Action Registry Lookup by ID

Have `useActionDispatch` fetch the full `ActionDef` from the registry API by ID, so callers pass only `actionId`:
```typescript
dispatch('harden-knowledge') // looks up label, dispatch mode, page from YAML
```

**Rejected for now**: Requires async lookup on every button render or a preloaded cache. Adds latency and complexity. The 3-argument form is sufficient to eliminate type duplication and inline construction. Can be added later as an enhancement.

### 2. Runtime Type Checking Instead of Build-Time

Use Zod or similar for runtime dispatch validation instead of TypeScript imports.

**Rejected**: The problem is build-time — TypeScript already has the type, it just isn't imported. Runtime validation adds bundle size for a problem that TypeScript solves for free.

---

## References

- ADR-130 — Action discovery from plugin YAML
- [ADR-160](ADR-160-oneshot-agent-bubbles.md) — Oneshot agent bubble dispatch
- [ADR-161](ADR-161-chat-context-injection-optimization.md) — Context injection optimization

---

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: useActionDispatch
      module: src/dashboard/hooks/useActionDispatch.ts
      breaking: false  # New hook, no existing callers
  patterns_deprecated:
    - grep: "dispatch: 'fire' \\| 'ide' \\| 'modal'"
      replacement: "import type { DispatchMode } from '@/lib/actions/types'"
    - grep: "dispatch: 'fire' \\| 'oneshot' \\| 'ide' \\| 'modal'"
      replacement: "import type { DispatchMode } from '@/lib/actions/types'"
    - grep: "const handleAction = async \\(actionId: string, label: string, dispatch:"
      replacement: "const { dispatch } = useActionDispatch()"
  files_affected:
    - glob: "plugins/*/skills/*/augur/dashboard/**/*.tsx"
    - glob: "src/dashboard/lib/services/cortex-graph.ts"    # DELETE
    - glob: "src/dashboard/lib/services/privacy.ts"          # DELETE
    - glob: "config/dashboard/list_shortcuts.yaml"           # DELETE
    - glob: "config/dashboard/path_aliases.yaml"             # DELETE
    - glob: "src/dashboard/hooks/useActionDispatch.ts"       # NEW
    - glob: "src/dashboard/lib/plugin-schema/types.ts"
    - glob: "src/dashboard/components/DetailPanel.tsx"
    - glob: "src/scripts/plugin-lint.py"
```
