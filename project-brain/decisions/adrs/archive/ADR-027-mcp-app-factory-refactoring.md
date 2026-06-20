---
status: Implemented
date: '2026-01-28'
deciders:
- Core team
related: []
hub: null
tags:
- mcp
- app
- factory
- refactoring
superseded_by: null
---

# ADR-027: MCP App Factory+ Refactoring

**Context**: MCP Apps specification release (January 2026)

## Context

MCP Apps (announced January 26, 2026) enable MCP tools to return rich, interactive UIs rendered in sandboxed iframes within AI chat interfaces like Claude Desktop. This creates an opportunity to enhance Augur's plugin factory to generate both traditional Next.js dashboard pages AND MCP App widgets.

The current `plugins/dev/` bundle contains:
- **mcp-app-factory**: Scaffolds new plugins with templates
- **design-system**: Provides 5 page block templates (overview, data-list, detail, settings, analytics)

The existing `dashboard.yaml` schema already has concepts that map well to MCP Apps:
- `modals` → Form widgets
- `metrics-grid` sections → Stat widgets
- `actions` → Tool triggers

## Decision

### 1. Bundle Rename
`plugins/dev/` → `plugins/mcp-app-factory+/`

The "+" suffix indicates this goes beyond a basic factory - it's an enhanced toolkit for building MCP Apps and dashboard extensions.

### 2. Template Categorization

| Old Template | New Type | New Name |
|--------------|----------|----------|
| `overview-page.tsx.template` | **MCP App** | `stat-widget.html.template` |
| `data-list-page.tsx.template` | **MCP App** | `data-table-widget.html.template` |
| `detail-page.tsx.template` | **MCP App** | `detail-card-widget.html.template` |
| `settings-page.tsx.template` | **MCP App** | `form-widget.html.template` |
| `analytics-page.tsx.template` | **Extension** | `analytics-extension.tsx.template` |

### 3. New Directory Structure

```
plugins/mcp-app-factory+/skills/
├── mcp-app-factory/
│   ├── templates/
│   │   ├── mcp-apps/                    # NEW
│   │   │   ├── stat-widget.html.template
│   │   │   ├── data-table-widget.html.template
│   │   │   ├── detail-card-widget.html.template
│   │   │   ├── form-widget.html.template
│   │   │   └── src/lib/
│   │   │       ├── app-base.html.template
│   │   │       ├── augur-styles.css.template
│   │   │       └── app-utils.js.template
│   │   └── ... (existing templates)
│   └── scripts/scaffold.py              # MODIFIED
│
└── design-system/
    └── templates/
        ├── mcp-apps/                    # NEW: MCP App widget templates
        └── extensions/                  # RENAMED from blocks/
            └── analytics-page.tsx.template
```

### 4. Dashboard.yaml Schema Update (v2.1)

Add `mcp_apps` section for auto-derivation:

```yaml
version: "2.1"

mcp_apps:
  # Auto-derived from existing modals
  forms:
    - id: add-job
      source: modal:add-job
      resource_uri: ui://career/forms/add-job

  # Auto-derived from metrics-grid sections
  widgets:
    - id: overview-stats
      source: tab:overview.sections[0]
      resource_uri: ui://career/widgets/overview-stats

  # Custom MCP Apps
  custom:
    - id: pipeline-table
      template: data-table-widget
      resource_uri: ui://career/widgets/pipeline-table
```

### 5. Scaffold.py Changes

- Add `mcp_apps` to VALID_FEATURES list
- Implement `generate_mcp_apps()` function
- Add auto-derivation from modals and metrics-grid
- Update directory creation for mcp-apps/

## Implementation Phases

### Phase 1: Create MCP App Templates (2-3 days)
- Create `mcp-apps/` directory structure
- Convert 4 page templates to MCP App HTML templates
- Create src/lib base templates (app-base, augur-styles, app-utils)

### Phase 2: Update Scaffold.py (1-2 days)
- Add `mcp_apps` feature flag
- Implement `generate_mcp_apps()` function
- Add auto-derivation logic

### Phase 3: Bundle Rename (1 day)
- Rename `plugins/dev/` → `plugins/mcp-app-factory+/`
- Update `mount-plugins.ts` PLUGIN_BUNDLES
- Update all internal imports/references
- **Clean break** - no backwards-compat symlinks

### Phase 4: Plugin Migration (ongoing, per-plugin)
- Update `dashboard.yaml.template` with mcp_apps section
- Migrate plugins one-by-one (manual/controlled approach)
- Test each plugin individually before moving to next

### Phase 5: Documentation & Testing (1 day)
- Update SKILL.md files
- Update design-system component registry
- Test MCP Apps in Claude Desktop (when SDK available)

## Consequences

### Positive

- **Claude Desktop Integration**: Plugins can provide rich UIs directly in chat
- **Code Reuse**: Existing dashboard.yaml config auto-derives MCP Apps
- **Clear Purpose**: Renamed bundle clarifies MCP focus
- **Dual Output**: Generate both dashboard and MCP App artifacts
- **Future-Proof**: Aligns with MCP standard for portable UIs

### Negative

- **Maintenance Burden**: Two template sets to maintain
- **Migration Effort**: Existing plugins need updates (one-by-one)
- **Bundle Rename**: Breaking change for any external references
- **Learning Curve**: Developers need to understand MCP Apps concepts

### Neutral

- Next.js Pages Unchanged: Dashboard extensions work as before
- Plugin Structure Same: Only template output format changes
- MCP Tools Compatible: Existing tools work without modification

## Alternatives Considered

### Alternative 1: Keep Separate Factories
Create a new `mcp-widgets-factory` bundle alongside existing `factory`.

**Rejected because**: Duplicates code, confuses where to add features, harder to maintain consistency.

### Alternative 2: MCP Apps Only
Remove Next.js page templates entirely, generate only MCP Apps.

**Rejected because**: Full dashboard pages provide richer experience, analytics and complex views don't fit widget model.

### Alternative 3: Runtime Conversion
Convert Next.js pages to MCP Apps at runtime instead of at generation time.

**Rejected because**: Complex to implement, performance overhead, loses type safety.

## Critical Files to Modify

| File | Change |
|------|--------|
| `plugins/dev/` | Rename to `plugins/mcp-app-factory+/` |
| `plugins/ai/skills/mcp-app-factory/scripts/scaffold.py` | Add mcp_apps feature |
| `plugins/ai/skills/mcp-app-factory/templates/dashboard.yaml.template` | Add mcp_apps section |
| `plugins/dev/skills/frontend/templates/blocks/` | Reorganize into mcp-apps/ and extensions/ <!-- design-system merged into frontend --> |
| `src/dashboard/scripts/mount-plugins.ts` | Update PLUGIN_BUNDLES |
| Plugin `dashboard.yaml` files | Add mcp_apps section (migrate one-by-one) |

## Verification

1. **Template Generation**: Run `python scaffold.py --name test-plugin --features mcp_apps` and verify MCP App HTML files are created
2. **Bundle Rename**: Run `npm run build` in dashboard and verify plugins still mount
3. **Dashboard.yaml**: Validate new schema with existing plugins
4. **MCP Apps**: Test HTML files open in browser and render correctly

## References

- [MCP Apps Specification](https://modelcontextprotocol.github.io/ext-apps/)
- ADR-008: Plugin System
- ADR-012: Plugin Extraction Guide
- ADR-022: Plugin Standardization
