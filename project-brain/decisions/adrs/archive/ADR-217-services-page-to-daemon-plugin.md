---
status: Implemented
date: '2026-03-04'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- move
- external
- services
- page
- settings
superseded_by: null
---

# ADR-217: Move External Services Page from Settings to Daemon Plugin

## Context

The `/settings/services` tab manages external MCP servers, CLI tools, and applications (ADR-077). Its architecture is split:

- **Backend (already in daemon plugin)**: `plugins/observability/skills/daemon/scripts/service_availability.py` checks MCP/CLI/App status
- **Actions (already in daemon plugin)**: `add-service` and `uninstall-service` actions dispatch to IDE agent
- **Data**: `config/integrations/external_mcp_registry.yaml` stores service definitions
- **Frontend (in core settings)**: `src/dashboard/app/settings/ai/tabs/ExternalServicesTab.tsx` + sub-components (`AddServiceInput`, `ServiceCardMenu`)
- **API route (in core)**: `src/dashboard/app/api/services/status/route.ts` calls the daemon Python script
- **Hook (in core)**: `src/dashboard/hooks/useServiceStatus.ts` polls the API
- **Tab registration (in core)**: `src/dashboard/lib/tabs/registry.ts` registers the "Services" tab in settings

The `add-service` action uses `dispatch: "ide"` which means it relies on LLM/IDE agent execution — this is a daemon-level capability, not a general setting. The page doesn't belong in `/settings` alongside genuinely general preferences like Storage, Memory, and Editors.

## Decision

Move the External Services page from `/settings/services` to the daemon plugin under Observability, making the frontend match where the backend already lives.

### Changes

1. **Move ExternalServicesTab + sub-components to daemon plugin**
   - `ExternalServicesTab.tsx` → `plugins/observability/skills/daemon/augur/dashboard/services/page.tsx`
   - `AddServiceInput.tsx` → `plugins/observability/skills/daemon/augur/dashboard/components/AddServiceInput.tsx`
   - `ServiceCardMenu.tsx` → `plugins/observability/skills/daemon/augur/dashboard/components/ServiceCardMenu.tsx`

2. **Move API route to daemon plugin**
   - `src/dashboard/app/api/services/status/route.ts` → `plugins/observability/skills/daemon/augur/api/services/status/route.ts`

3. **Register in `augur.yaml`** — Add `services` page contribution + tab entry

4. **Remove from settings** — Remove the "Services" tab from `coreTabRegistry.settings.tabs` and delete `src/dashboard/app/settings/services/page.tsx`

5. **Keep hook in core** — `useServiceStatus` stays in `src/dashboard/hooks/` since other skill pages may use it to check service availability

### File Impact

| Action | File |
|--------|------|
| Move | `src/dashboard/app/settings/ai/tabs/ExternalServicesTab.tsx` → daemon plugin dashboard |
| Move | `src/dashboard/app/settings/ai/tabs/AddServiceInput.tsx` → daemon plugin components |
| Move | `src/dashboard/app/settings/ai/tabs/ServiceCardMenu.tsx` → daemon plugin components |
| Move | `src/dashboard/app/api/services/status/route.ts` → daemon plugin API |
| Modify | `plugins/observability/skills/daemon/augur.yaml` (add page + tab) |
| Modify | `src/dashboard/lib/tabs/registry.ts` (remove Services tab from settings) |
| Delete | `src/dashboard/app/settings/services/page.tsx` |

## Consequences

### Positive

- Full stack locality — frontend, API, backend script, and actions all in one plugin
- Settings page loses its daemon/LLM dependency
- Stronger adherence to ADR-163 (plugin decentralization)
- External services management can grow alongside daemon capabilities

### Negative

- Users must navigate to Observability > Daemon > Services instead of Settings > Services
- API path changes from `/api/services/status` to `/api/observability/daemon/services/status`

### Neutral

- `useServiceStatus` hook stays in core (other pages consume it)
- `external_mcp_registry.yaml` stays in `config/integrations/`

## References

- ADR-077: External Service Integration
- ADR-163: Plugin Decentralization
- Backend: `plugins/observability/skills/daemon/scripts/service_availability.py`
- Actions: `plugins/observability/skills/daemon/augur/data/actions/add-service.yaml`
