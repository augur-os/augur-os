---
status: Implemented
date: '2026-03-04'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- llm
- driven
- service
- manager
superseded_by: null
---

# ADR-214: LLM-Driven Service Manager

## Context

The `/settings/services` page (`ExternalServicesTab`) displays external services (MCP servers, CLI tools, macOS apps) with status badges and a basic remove button, but lacks the ability to add new services, offers no two-tier removal (quick remove vs full uninstall), and cannot clean up installed packages, running processes, and config files from the machine.

Users need a way to:
1. Install new external services by providing a URL, package name, or description
2. Remove services from Augur's registry without touching the machine
3. Fully uninstall services — killing processes, removing packages, cleaning configs, and deleting registry entries

## Decision

Implement an LLM-driven service manager where all heavy operations (add, full uninstall) are dispatched to the IDE agent via `dispatch: 'ide'`. The dashboard never calls LLM APIs directly, following Augur's standard `useActionRunner` pattern.

### UI Changes

1. **"Add Service" button** in the header bar, toggling an `AddServiceInput` component with a text input for URLs, package names, or descriptions
2. **Enhanced service cards** with a dropdown menu offering "Remove from Augur" (quick) and "Full Uninstall" (LLM-driven)
3. **Action progress** shown via the existing IDE dispatch flow (toast notifications, ActionDialogView)

### Add Service Flow

User provides input (URL/name/description) → IDE agent analyzes it → determines service type (MCP/CLI/app) → installs via appropriate package manager → registers in `external_mcp_registry.yaml` with `install_method` and `install_source` metadata fields.

### Remove/Cleanup Flow

**Tier 1 (Remove from Augur):** Direct API call to delete registry entry. No LLM needed.

**Tier 2 (Full Uninstall):** IDE agent kills processes, uninstalls packages (brew/npm/pip), removes config entries (`.mcp.json`, env vars), cleans cached data, and removes registry entry.

### Action Definitions

Two new action YAMLs in `plugins/observability/skills/daemon/augur/data/actions/`:
- `add-service.yaml` — `dispatch: ide`, prompt for installation analysis
- `uninstall-service.yaml` — `dispatch: ide`, prompt for full cleanup with confirmation

### Registry Schema Extension

New fields in `external_mcp_registry.yaml` entries:
- `install_method`: npm | brew | pip | git | manual | app-store
- `install_source`: original URL or package name provided by user

## Consequences

### Positive

- Users can add any external service from a URL or package name without manual config editing
- Two-tier removal gives users control over cleanup scope
- LLM-driven approach handles diverse service types elegantly without hardcoded recipes
- Follows existing architecture (IDE dispatch, `useActionRunner`)

### Negative

- Requires IDE connection for add/uninstall operations (not available in remote sessions without workaround)
- LLM may make mistakes on unfamiliar tools (non-deterministic)
- Full uninstall modifies system state (shell profiles, global packages) — requires user confirmation

### Neutral

- Existing service status display, search, filter, and polling remain unchanged
- The DELETE API endpoint already partially exists and needs minor enhancement

## Alternatives Considered

### Alternative 1: Script-Based Service Manager

Structured wizard form for adding, hardcoded uninstall recipes per service type. Deterministic and offline-capable, but rigid — can't handle unknown tools, lots of edge cases to code, poor UX.

### Alternative 2: Hybrid (LLM Add + Script Remove)

LLM-driven add with deterministic script-based removal using stored install metadata. Reliable cleanup but more complex metadata tracking, and scripts can't adapt to unexpected system state.

## References

- Design doc: `docs/plans/2026-03-04-service-manager-design.md`
- Implementation plan: `docs/plans/2026-03-04-service-manager-impl.md`
- ADR-077: External service integration
- ADR-130: Action dispatch modes
- Registry: `config/integrations/external_mcp_registry.yaml`
- Current UI: `src/dashboard/app/settings/ai/tabs/ExternalServicesTab.tsx`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using the implementation plan.

**Team name**: `adr-214-impl`

### Phase 1: Action Definitions
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend | low | Create add-service action YAML | `plugins/observability/skills/daemon/augur/data/actions/add-service.yaml` |
| 1.2 | backend | low | Create uninstall-service action YAML | `plugins/observability/skills/daemon/augur/data/actions/uninstall-service.yaml` |

### Phase 2: UI Components
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Build AddServiceInput component | `src/dashboard/app/settings/ai/tabs/AddServiceInput.tsx` |
| 2.2 | frontend | medium | Build ServiceCardMenu dropdown | `src/dashboard/app/settings/ai/tabs/ServiceCardMenu.tsx` |

### Phase 3: Integration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Integrate components into ExternalServicesTab | `src/dashboard/app/settings/ai/tabs/ExternalServicesTab.tsx` |
| 3.2 | frontend | low | Add install metadata fields to ServiceStatus type | `src/dashboard/hooks/useServiceStatus.ts` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | TypeScript check, verify no regressions |
| V.2 | validator | low | Browser verification of add/remove/uninstall flows |

### Completion Criteria
- [ ] All phases executed
- [ ] TypeScript compiles without new errors
- [ ] Add Service input renders and dispatches IDE action
- [ ] Service cards show dropdown with Remove/Full Uninstall
- [ ] Action YAMLs are discoverable by loadAllActions()
- [ ] ADR status updated to Accepted/Implemented
