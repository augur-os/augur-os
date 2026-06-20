---
status: Implemented
date: '2026-02-11'
deciders:
- Gur Sannikov
related:
- ADR-005 (MCP Gateway)
- ADR-006 (Local-First)
- ADR-018 (Plugin Self-Containment)
- ADR-059 (MCP Context Focus)
- ADR-063 (MCP Hardening)
hub: null
tags:
- external
- services
- integration
superseded_by: null
---

# ADR-077: External Services Integration

## Context

Augur skills operate in isolation — they read local YAML databases, call the augur MCP server, and render dashboards. But real-world life automation requires reaching beyond local data. A career skill that can only display jobs you manually entered is fundamentally limited compared to one that scrapes LinkedIn for roles matching your profile. A finance skill that can only chart data you typed is less useful than one that pulls live portfolio values.

### What are "external services"?

External services are capabilities outside the augur monorepo that a skill can leverage:

| Type | Examples | Transport |
|------|----------|-----------|
| **MCP servers** (remote) | BrightData, Exa, Firecrawl, Brave Search | stdio/SSE via MCP protocol |
| **MCP servers** (local) | Chrome MCP, filesystem, SQLite | stdio via MCP protocol |
| **Local CLIs** | `gog` (Google Workspace), `gh` (GitHub), `yt-dlp`, `ffmpeg` | subprocess |
| **Local programs** | Raycast, Shortcuts.app, Automator | AppleScript / URL scheme |
| **REST APIs** | Weather APIs, stock APIs, RSS feeds | HTTP (no auth or API key) |

### Current state

The infrastructure exists in pieces but lacks a cohesive integration contract:

1. **`external_mcp_registry.yaml`** — defines 6 MCP servers (only context7 enabled). Static config, no runtime availability concept.
2. **`SKILL.md` frontmatter `mcp_servers:`** — skills declare MCP dependencies. But there's no runtime check — if BrightData is declared but not connected, the skill has no way to know.
3. **`configure_mcp.py`** — scans SKILL.md files and applies MCP configs to IDEs. Build-time only, no runtime feedback.
4. **`dashboard.yaml` actions** — can reference `mcp_tool:` but have no conditional visibility based on service availability.
5. **`mcp_tool_groups.yaml`** — scopes tools per page. No concept of "available if external service X is connected".

### The gap

| What exists | What's missing |
|------------|----------------|
| Static registry of external servers | Runtime availability detection |
| Skill-level MCP declarations | Conditional UI based on service availability |
| IDE-level MCP configuration | Health probes for external services |
| Page-level tool scoping | Graceful degradation when services are down |
| — | Discovery: "what services could enhance this skill?" |
| — | Security contract: what data leaves the local system? |

### Real scenarios that don't work today

1. **Career + BrightData**: Career dashboard has a "Scan LinkedIn" button. If BrightData MCP isn't connected, clicking it fails silently. Should: hide the button, or show it disabled with "Connect BrightData to enable".
2. **Content + Firecrawl**: Content skill wants to scrape articles for summarization. Firecrawl is one option, BrightData is another, and `curl` is a fallback. No way to express this service preference chain.
3. **Finance + Stock API**: Finance skill could pull live prices. But the skill can't declare "I need HTTP access to api.example.com" — only MCP servers are tracked.
4. **Google Workspace + `gog` CLI**: Already works via subprocess, but not registered as an "external service" — it's invisible to the availability system.

## Decision

### 1. Unified service manifest per skill

Extend `SKILL.md` frontmatter to declare all external dependencies (not just MCP servers):

```yaml
---
name: career
version: 1.1.0
services:
  required: []  # Skill won't function without these
  optional:
    - id: brightdata
      type: mcp
      purpose: "LinkedIn job scraping and market research"
      features:
        - scan-linkedin-jobs
        - company-research
      fallback: null  # No alternative
    - id: exa
      type: mcp
      purpose: "Semantic search for job listings across the web"
      features:
        - smart-job-search
      fallback: brave-search  # Can use Brave Search instead
  cli:
    - id: gh
      command: gh
      purpose: "GitHub profile enrichment for job applications"
      check: "gh --version"
---
```

**Key design choices**:
- `required` vs `optional` — skills degrade gracefully, required services block skill activation
- `features` — maps service to specific dashboard features (actions/tabs that depend on it)
- `fallback` — expresses service preference chains
- `cli` section — brings local CLIs into the same availability system
- `type` field — `mcp`, `cli`, `api`, `app` (extensible)

### 2. Runtime availability API

Add a `/api/services/status` endpoint and MCP tool that reports what's actually available:

```typescript
// GET /api/services/status?skill=career
{
  "skill": "career",
  "services": {
    "brightdata": {
      "status": "disconnected",       // connected | disconnected | degraded | unknown
      "type": "mcp",
      "features_blocked": ["scan-linkedin-jobs", "company-research"],
      "setup_hint": "Enable in Settings > Integrations > Bright Data"
    },
    "exa": {
      "status": "disconnected",
      "type": "mcp",
      "fallback": { "id": "brave-search", "status": "disconnected" },
      "features_blocked": ["smart-job-search"]
    },
    "gh": {
      "status": "connected",
      "type": "cli",
      "version": "2.45.0"
    }
  },
  "health": "partial"  // full | partial | degraded | offline
}
```

**How availability is detected**:

| Type | Health Check Method |
|------|-------------------|
| MCP server | Check if server ID exists in active MCP session tools list (via `list-mcp-tools`) |
| CLI | Run the `check` command (e.g., `gh --version`), cache result for 5 minutes |
| API | HTTP HEAD to base URL, cache result for 5 minutes |
| App | Check if app bundle exists on disk (macOS: `mdfind kMDItemCFBundleIdentifier`) |

### 3. Conditional dashboard features

Extend `dashboard.yaml` to gate actions/tabs on service availability:

```yaml
actions:
  - id: scan-linkedin-jobs
    label: "Scan LinkedIn"
    icon: Search
    flow: llm
    mode: ide
    requires_service: brightdata  # Hidden or disabled when unavailable
    unavailable_label: "Connect Bright Data to enable"
    mcp_tools:
      - brightdata-scrape
      - brightdata-search
    context: "Use BrightData MCP to search LinkedIn for {{role}} jobs in {{location}}"

  - id: smart-job-search
    label: "Smart Job Search"
    icon: Sparkles
    flow: llm
    requires_service: [exa, brave-search]  # Any one suffices (OR logic)
    context: "Search for jobs matching profile using available search service"
```

**UI behavior**:

| Service status | Button behavior |
|---------------|----------------|
| `connected` | Normal — clickable, full color |
| `disconnected` | Grayed out with tooltip: "Connect X to enable" |
| `degraded` | Yellow warning icon, still clickable |
| `unknown` | Normal but with (?) indicator |

### 4. Service integration registry (extend external_mcp_registry.yaml)

Evolve the existing registry to `v2` with broader service types:

```yaml
version: 2
services:
  # MCP servers (existing, migrated from v1)
  brightdata:
    name: Bright Data
    type: mcp
    description: Web scraping and data collection via Bright Data proxies
    tier: 2
    cost: existing
    enabled: false
    command: npx
    args: ['-y', '@anthropics/brightdata-mcp']
    env:
      API_TOKEN: ${BRIGHTDATA_API_KEY}
    env_required:
      - name: BRIGHTDATA_API_KEY
        description: Bright Data API key
    tags: [scraping, proxy, web, linkedin]
    used_by: [career, install, content]  # NEW: which skills use this
    setup_url: "https://brightdata.com/docs/mcp"  # NEW: onboarding link

  # Local CLIs (NEW)
  gh:
    name: GitHub CLI
    type: cli
    description: GitHub repository and profile operations
    cost: free
    enabled: auto  # auto-detected via `which gh`
    check_command: "gh --version"
    tags: [github, git]
    used_by: [career, developer]

  gog:
    name: Google Workspace CLI
    type: cli
    description: Gmail, Calendar, Drive operations
    cost: free
    enabled: auto
    check_command: "gog version"
    tags: [google, email, calendar]
    used_by: [google-workspace]

  # Local apps (NEW)
  raycast:
    name: Raycast
    type: app
    description: Launcher and automation
    cost: free
    enabled: auto
    bundle_id: com.raycast.macos
    tags: [automation, launcher]
    used_by: [home-automation]
```

**v1 → v2 migration**: Backward compatible. Missing fields get defaults (`type: mcp`, `used_by: []`, `enabled: false`).

### 5. Settings > Integrations dashboard page

Add an Integrations page to the dashboard that:

1. Lists all services from the registry with their status (connected/disconnected)
2. Groups by type (MCP Servers, CLIs, Apps)
3. Shows which skills each service enables
4. Provides setup links/instructions for disconnected services
5. Lets users enable/disable services (writes to registry)

This replaces the current "figure it out from YAML files" workflow with a visual integration manager.

### 6. Data flow boundaries (security contract)

Each service declaration includes a `data_scope` field defining what data the skill may send:

```yaml
services:
  optional:
    - id: brightdata
      type: mcp
      data_scope:
        sends: [job_title, location, company_name]  # What leaves local system
        receives: [job_listings, company_info]        # What comes back
        never_sends: [resume_content, salary_info, personal_contacts]
```

This is **advisory, not enforced** in v1 — it documents intent for user awareness. The Settings > Integrations page shows data flow for each connected service so users understand what information leaves their system.

This aligns with ADR-006 (local-first): external services are opt-in enhancements, never requirements for core functionality.

## Consequences

### Positive

- Skills can leverage external capabilities while degrading gracefully when services are unavailable
- Users see exactly what's available and what connecting a service would unlock
- Unified model for MCP servers, CLIs, and apps — no more invisible dependencies
- Data flow transparency supports the local-first privacy commitment
- Fallback chains allow skills to use the best available service

### Negative

- Runtime availability checks add latency to dashboard page loads (mitigated by 5-minute caching)
- Service registry is another config file to maintain
- `data_scope` is advisory-only in v1 — no runtime enforcement
- CLI availability depends on user's PATH — may give false negatives in some environments

### Neutral

- Existing `mcp_servers:` frontmatter in SKILL.md continues to work (auto-migrated to `services.optional` format)
- `configure_mcp.py` continues to handle IDE-level MCP configuration — this ADR adds runtime visibility on top
- No changes to MCP protocol itself — this is an augur-level orchestration layer

## Alternatives Considered

### Alternative 1: MCP-only (ignore CLIs and apps)

Only track MCP servers since they have a standard protocol. Rejected because:
- Many valuable integrations are CLIs (`gh`, `gog`, `yt-dlp`) not MCP servers
- The availability problem is the same regardless of transport
- Would require wrapping every CLI in an MCP server — unnecessary overhead

### Alternative 2: Plugin marketplace / store model

Build a marketplace where users browse and install service integrations. Rejected because:
- Premature — only 6 external services exist today
- Over-engineers the discovery problem (a settings page suffices)
- Violates "address simple high-leverage improvements before complex infrastructure"

### Alternative 3: Auto-discovery via MCP tool listing

Detect available services at runtime by listing all MCP tools and matching them to known service signatures. Rejected as primary mechanism because:
- Unreliable — tool names aren't standardized across MCP servers
- Doesn't work for CLIs and apps
- But IS used as a secondary signal for MCP availability checks

## References

- ADR-005: MCP as Execution Gateway
- ADR-006: Local-First Architecture
- ADR-018: Plugin Self-Containment
- ADR-059: MCP Context Focus & Skill-Aware Tool Scoping
- ADR-063: MCP Implementation Hardening
- Existing: `config/integrations/external_mcp_registry.yaml`
- Existing: `scripts/configure_mcp.py`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-077: External Services Integration**.

Read the full ADR: `docs/decisions/ADR-077-external-services-integration.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-077-external-services", description="Implementing ADR-077: External Services Integration")`
2. **Create tasks**: For each step, create a task via `TaskCreate`. Set `blocked_by` for dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate with their profile from `.claude/agents/{role}.md`
4. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` → haiku, `medium` → sonnet, `high` → opus

### Execution Plan

**Team name**: `adr-077-external-services`

#### Phase 1: Service Manifest & Registry v2
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Migrate `external_mcp_registry.yaml` from v1 to v2 — add `type`, `used_by`, `setup_url` fields to existing entries. Add CLI entries for `gh`, `gog`. Maintain backward compatibility. | `config/integrations/external_mcp_registry.yaml` |
| 1.2 | developer | medium | Create `service_availability.py` in daemon scripts — implement health checks for each service type (MCP: list-tools check, CLI: check_command exec, App: bundle_id lookup). 5-minute cache. | `plugins/observability/skills/daemon/scripts/service_availability.py` |
| 1.3 | developer | low | Update `SKILL.md` frontmatter parser in `configure_mcp.py` to support new `services:` block alongside legacy `mcp_servers:`. Auto-migrate legacy format. | `scripts/configure_mcp.py` |

#### Phase 2: Runtime API & MCP Tool
**Strategy**: PIPELINE (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Add `service-status` MCP tool to augur-mcp server — calls `service_availability.py`, returns per-skill service status. Optional `skill` filter parameter. | `src/mcp/augur_mcp/server.py` |
| 2.2 | developer | medium | Add `/api/services/status` Next.js API route — proxies to `service_availability.py` for dashboard consumption. Query param `?skill=career` for filtering. | `src/dashboard/app/api/services/status/route.ts` |

#### Phase 3: Dashboard Integration
**Strategy**: PARALLEL (depends on Phase 2)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Create `useServiceStatus` React hook — fetches `/api/services/status`, caches in React Query, exposes `isServiceAvailable(serviceId)` helper. | `src/dashboard/hooks/useServiceStatus.ts` |
| 3.2 | frontend | medium | Create `ServiceGatedAction` wrapper component — wraps action buttons, checks `requires_service` against availability, renders disabled state with setup hint tooltip when unavailable. | `src/dashboard/components/ServiceGatedAction.tsx` |
| 3.3 | frontend | medium | Create Integrations settings page — lists all services grouped by type, shows status badges, links to setup docs, toggle enable/disable. | `plugins/observability/skills/daemon/dashboard/tabs/IntegrationsTab.tsx` |

#### Phase 4: Career Skill Integration (Proof of Concept)
**Strategy**: PIPELINE (depends on Phase 3)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Update career `SKILL.md` frontmatter to new `services:` format. Add BrightData, Exa, and `gh` CLI declarations with features, fallbacks, and data_scope. | `plugins/career/skills/career/SKILL.md` |
| 4.2 | frontend | medium | Update career `dashboard.yaml` — add `requires_service` to LinkedIn-related actions. Add "Scan LinkedIn Jobs" action gated on brightdata. | `plugins/career/skills/career/augur.yaml` |

#### Final Phase: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `pytest tests/` — verify no regressions |
| V.2 | validator | low | Run `npm run build` in `src/dashboard/` — verify dashboard builds cleanly |
| V.3 | validator | low | Run `python3 scripts/configure_mcp.py --dry-run` — verify legacy and v2 format both parse |
| V.4 | validator | low | Verify `service-status` MCP tool returns valid JSON for career skill |

### Completion Criteria
- [ ] Registry v2 schema implemented with backward compatibility
- [ ] `service_availability.py` checks MCP, CLI, and app service types
- [ ] `service-status` MCP tool works
- [ ] `/api/services/status` API route works
- [ ] `useServiceStatus` hook and `ServiceGatedAction` component exist
- [ ] Integrations settings page renders service list
- [ ] Career skill uses new `services:` format
- [ ] Career dashboard gates LinkedIn actions on BrightData availability
- [ ] All tests pass
- [ ] ADR-077 status updated to Accepted
