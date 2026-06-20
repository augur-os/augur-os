---
status: Implemented
date: '2025-01-27'
deciders:
- Core team
related: []
hub: null
tags:
- plugin
- shared
- services
- architecture
superseded_by: null
---

# ADR-026: Plugin Shared Services Architecture

## Context

Plugin API routes are mounted into `src/dashboard/app/api/` at build time via `mount-plugins.ts`. When these routes execute, they run in the dashboard context and use `@/lib` imports (which resolve to `src/dashboard/lib/`).

This creates a problem: services that are logically owned by plugins must physically live in `src/dashboard/lib/services/` for imports to work at runtime.

**Current state**:
```
src/dashboard/lib/services/
├── rag-projects.ts    # OWNER: knowledge plugin, CONSUMERS: capture, knowledge
├── chains.ts          # OWNER: agent-manager, CONSUMERS: agents API
├── chains-yaml.ts     # Supporting file for chains.ts
└── chain-telemetry.ts # Supporting file for chains.ts
```

**Problems**:
1. **Ownership confusion** - Files in dashboard that are owned by plugins
2. **Dependency inversion** - Core depends on plugin code
3. **No isolation** - Plugin services can accidentally depend on each other
4. **Discovery** - Hard to find plugin-specific code

## Decision

Implement **Plugin Lib Mounting** - extend the existing `mount-plugins.ts` to also mount plugin `lib/` directories.

### Implementation

**1. Plugin lib directory structure**:
```
plugins/ai/skills/knowledge/
├── api/           # Mounted to dashboard/app/api/knowledge/
├── dashboard/     # Mounted to dashboard/app/knowledge/
└── lib/           # NEW: Mounted to dashboard/lib/plugins/services/
    └── rag-projects.ts
```

**2. Mount target**:
```
src/dashboard/lib/plugins/
├── knowledge/
│   └── rag-projects.ts
├── agent-manager/
│   ├── chains.ts
│   ├── chains-yaml.ts
│   └── chain-telemetry.ts
└── [plugin-name]/
    └── [service].ts
```

**3. Import pattern**:
```typescript
// Before (confusing - plugin code in core)
import { createRagProject } from '@/lib/services/rag-projects';

// After (clear ownership)
import { createRagProject } from '@/lib/plugins/services/rag-projects';
```

**4. Update mount-plugins.ts**:
```typescript
// Add to PLUGIN_MOUNT_CONFIG
{
  source: 'lib',
  target: 'lib/plugins/{plugin-name}',
  pattern: '**/*.ts',
}
```

**5. Gitignore**:
```
# src/dashboard/.gitignore
/lib/plugins/  # Mounted from plugins, don't edit directly
```

## Consequences

### Positive

- **Clear ownership** - Plugin code lives in plugin directories
- **Discoverable** - `lib/plugins/services/` clearly shows plugin origin
- **Consistent** - Same mounting pattern as API routes and pages
- **Isolated** - Each plugin's lib is separate
- **Type-safe** - TypeScript still works with `@/lib/plugins/*` imports

### Negative

- **Build complexity** - More files to mount
- **Import path changes** - Existing code needs updates
- **Cross-plugin imports** - Plugins importing from other plugins need explicit paths

### Neutral

- **Runtime behavior unchanged** - Still runs in dashboard context
- **Same file count** - Just moved, not duplicated

## Alternatives Considered

### Alternative 1: Shared Packages (`plugins/src/lib-services/`)

Create a separate npm package for src/lib services.

```
plugins/src/lib-services/
├── package.json
├── src/
│   ├── rag-projects.ts
│   └── chains.ts
└── tsconfig.json
```

**Rejected because**:
- Adds npm dependency management complexity
- Services are plugin-specific, not truly src/lib
- Requires separate build step
- Overkill for internal code sharing

### Alternative 2: MCP-Based Services

Move services to MCP tools, call via API instead of import.

```typescript
// Instead of import
const projects = await mcpClient.call('knowledge.list-rag-projects');
```

**Rejected because**:
- Performance overhead (HTTP vs direct call)
- Async boundary for simple operations
- Complicates error handling
- Not all services are suitable for MCP

### Alternative 3: Runtime Path Resolution

Use dynamic imports with runtime path resolution.

```typescript
const service = await import(`@plugins/${pluginName}/lib/service`);
```

**Rejected because**:
- Loses TypeScript type checking
- Dynamic imports complicate bundling
- Harder to trace dependencies
- Runtime errors instead of build errors

### Alternative 4: Keep Current + Comments (Status Quo)

Keep files in `lib/services/` with ownership comments.

**Rejected because**:
- Doesn't solve the architectural issue
- Ownership comments can become stale
- Still confusing for new developers
- Violates separation of concerns

## Migration Plan

1. **Phase 1**: Update `mount-plugins.ts` to support lib mounting
2. **Phase 2**: Move existing services to plugin lib directories
3. **Phase 3**: Update all imports to use `@/lib/plugins/*` pattern
4. **Phase 4**: Delete old `lib/services/` files that moved
5. **Phase 5**: Add lint rule to prevent new files in `lib/services/` for plugin code

## References

- ADR-012: Plugin Mounting System
- ADR-022: Plugin Standardization
- `src/dashboard/scripts/mount-plugins.ts` - Current mounting implementation
