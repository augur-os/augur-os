---
status: Implemented
date: '2026-02-26'
deciders:
- Project team
related:
- ADR-126 (plugin structure)
- ADR-130 (action discovery)
- ADR-162 (type consolidation)
hub: null
tags:
- config
- decentralization
superseded_by: null
---

# ADR-163: Config Decentralization

---

## Context

Augur's architecture claims each plugin is self-contained, but four centralized config files in `config/dashboard/` violate this by aggregating plugin-specific data into hand-maintained registries:

| File | Lines | What it centralizes | Plugin-level alternative |
|------|-------|--------------------|-----------------------|
| `mcp_tool_groups.yaml` | ~450 | 30 skill→tool mappings, page→tool scoping | `augur.yaml` `mcp_tools:` section |
| `tool_display_names.yaml` | ~200 | 65 tool display names, icons, categories | `augur.yaml` `mcp_tools.display:` section |
| `mcp_tools.yaml` | varies | Tool metadata | `augur.yaml` `mcp_tools:` section |
| `app_mode.yaml` | varies | Operation/dev mode tool visibility | `augur.yaml` `mcp_tools.modes:` section |

### Why this is the #1 architectural problem

1. **Drift**: When a plugin adds a new MCP tool, the developer must remember to also update 2-3 central YAML files. They never do. Result: tools exist but have no display name, no page scoping, no mode visibility.

2. **Merge conflicts**: Multiple ADR implementations touching different plugins all edit the same central files, creating unnecessary merge conflicts.

3. **Ownership ambiguity**: Who owns `mcp_tool_groups.yaml`? No plugin. It's orphaned config that nobody maintains, so it rots. The comment on line 5 literally says "will be auto-generated from dashboard.yaml in ADR-105" — that was never done.

4. **Anti-pattern entrenchment**: ADR-162 nearly added validation for these centralized files, which would have made them "more correct" and reduced pressure to decentralize. Any work that improves centralized config entrenches it.

5. **Discovery already works**: Action discovery (ADR-130) already walks `plugins/*/skills/*/augur/data/actions/*.yaml` — proving the decentralized discovery pattern works. Tool config should follow the same pattern.

### The existing decentralized pattern (actions)

```
plugins/career/skills/career/augur/data/actions/research-company.yaml
  → discovered by src/dashboard/lib/actions/discovery.ts
  → assembled at runtime, cached 30s
  → no central registry needed
```

This is the pattern that tool config should follow.

---

## Decision

### 1. Extend `augur.yaml` with MCP tool declarations

Each plugin declares its own tool metadata in its existing `augur.yaml`:

```yaml
# plugins/productivity/skills/apple/augur.yaml (existing file, new section)
mcp_tools:
  # Tool groups for this skill (replaces mcp_tool_groups.yaml entries)
  groups:
    - name: note-tools
      tools: [note-search, note-create, note-sync, note-edit, note-list]

  # Display names for tools this skill registers (replaces tool_display_names.yaml entries)
  display:
    note-search:
      displayName: Search Notes
      icon: Search
      category: productivity
    note-create:
      displayName: Create Note
      icon: Plus
      category: productivity

  # Mode visibility (replaces app_mode.yaml entries)
  modes:
    operation_hidden: [note-sync]  # hidden in operation mode, visible in dev
```

### 2. Add tool discovery to mount-plugins

Extend `src/dashboard/scripts/mount-plugins.ts` with a tool assembly step:

1. Walk `plugins/*/skills/*/augur.yaml`
2. Parse each `mcp_tools:` section
3. Assemble into `config/dashboard/generated/assembled_tool_config.json` (generated, not hand-edited)
4. Dashboard reads the generated file instead of the hand-maintained YAMLs

This follows the existing pattern: `mount-plugins.ts` already generates `assembled_hubs.json`.

### 3. Migrate existing centralized config into plugins

For each entry in the centralized YAML files:
1. Identify which plugin owns the tool (from `skill_tool_groups` mapping or MCP registration)
2. Add the `mcp_tools:` section to that plugin's `augur.yaml`
3. Remove the entry from the centralized file

After all entries are migrated, the centralized files become empty and can be deleted.

### 4. Page-level tool scoping via hub assembly

The `page_tool_groups` section in `mcp_tool_groups.yaml` maps pages to tool sets. This is replaced by:
- Each plugin declares which hub it belongs to (already in `augur.yaml`)
- `assembled_hubs.json` already maps hubs to skills
- Tool scoping derived from: page → hub → skills in hub → tools in those skills

No separate page→tool mapping needed.

### 5. Core tools remain in a single declaration

The `core_tools` list (tools loaded on every page) stays as a single declaration, but moves from `mcp_tool_groups.yaml` to `src/mcp/augur_mcp/core/core_tools.yaml` — owned by the MCP server, not dashboard config.

---

## Consequences

### Positive
- **Self-contained plugins**: Adding a new MCP tool requires editing only the plugin's `augur.yaml` — zero central files
- **Zero merge conflicts**: Plugins don't compete for lines in shared files
- **Auto-discovery**: New plugins automatically have their tools scoped, displayed, and mode-filtered
- **Single ownership**: Each tool's metadata lives next to its implementation

### Negative
- **Migration effort**: ~30 skill `augur.yaml` files need `mcp_tools:` sections added
- **Build step**: Tool assembly adds ~100ms to mount-plugins (acceptable — action discovery takes similar time)

### Neutral
- Dashboard code changes are minimal — just read from `assembled_tool_config.json` instead of individual YAML files
- MCP server tool registration is unchanged — this ADR only affects dashboard-side metadata

---

## Alternatives Considered

### 1. Validate centralized config and keep it

Add lint checks to ensure `mcp_tool_groups.yaml` stays correct.

**Rejected**: This was attempted in ADR-162 and reverted. Validating centralized config entrenches it. The root cause is centralization, not stale references.

### 2. Auto-generate centralized files from plugin declarations

Each plugin declares tools in `augur.yaml`, a script generates the centralized YAML.

**Rejected partially**: The generated output should be JSON (like `assembled_hubs.json`), not YAML that looks hand-editable. Generated YAML invites manual edits that get overwritten. The chosen approach generates JSON with a clear "DO NOT EDIT" header.

---

## References

- ADR-126 — Plugin directory structure
- ADR-130 — Decentralized action discovery pattern
- [ADR-162](ADR-162-action-type-consolidation-dead-code-elimination.md) — Type consolidation (reverted centralized validation)

---

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - function: loadToolGroups
      module: src/dashboard/app/api/registry/route.ts
      breaking: true  # reads from generated JSON instead of YAML
  patterns_deprecated:
    - grep: "mcp_tool_groups\\.yaml"
      replacement: "assembled_tool_config.json (generated by mount-plugins)"
    - grep: "tool_display_names\\.yaml"
      replacement: "augur.yaml mcp_tools.display section per plugin"
  files_affected:
    - glob: "plugins/*/skills/*/augur.yaml"
    - glob: "config/dashboard/mcp_tool_groups.yaml"        # DELETE after migration
    - glob: "config/dashboard/tool_display_names.yaml"      # DELETE after migration
    - glob: "config/dashboard/mcp_tools.yaml"               # DELETE after migration
    - glob: "config/dashboard/app_mode.yaml"                # DELETE after migration
    - glob: "src/dashboard/scripts/mount-plugins.ts"
    - glob: "src/dashboard/app/api/registry/route.ts"
```
