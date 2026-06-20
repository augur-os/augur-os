---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related: [ADR-452, ADR-451, ADR-404, ADR-158, ADR-266]
hub: null
tags: [dashboard, mcp-first, vault, fs-bypass, prevention-gates, eslint]
superseded_by: null
---

# ADR-453: Dashboard Vault Decoupling + Prevention Gates

## Context

Dashboard API routes access vault files in two fragile ways that cause recurring bugs:

1. **Data files read by hardcoded path** — ideas, notes, plans fetched via resolved vault paths. When files move during skill/hub reorganization, pages break silently.

2. **~13 API routes bypass MCP with direct `fs` calls** — `readFile`, `writeFile`, `readdir`, `stat` used directly in `route.ts` files, violating CLAUDE.md rule #11 ("MCP-first API"). No audit trail, inconsistent error handling, path resolution duplicated across routes.

3. **No prevention mechanism** — the same violations keep recurring because nothing catches new `fs` access in routes at commit or CI time.

ADR-452 established content-based vault discovery via `sync_discover.py` for sync targets. This ADR extends that pattern to dashboard data consumption and eliminates all remaining fs access.

## Decision

Three components:

### Component A: Vault Data Discovery MCP Tools

Extend `sync_discover.py` (ADR-452) with a `data_source` frontmatter field and expose `vault-data-query` / `vault-data-list` MCP tools. Dashboard API routes call these instead of hardcoded file reads.

New frontmatter on vault files consumed by dashboard:

```yaml
data_source: dashboard       # triggers discovery
data_type: ideas             # semantic type for querying
```

New MCP tools:

| Tool | Purpose | Parameters |
|------|---------|------------|
| `vault-data-query` | Read a specific vault data file by type+skill | `data_type`, `skill`, `title` |
| `vault-data-list` | List all vault data files, optionally filtered | `data_type`, `skill` |

Named `vault-data-*` to distinguish from existing `vault-status` (git/sync health).

### Component B: Rewire All fs-Bypass Routes to MCP

**Verified fs-bypass routes (grep-confirmed):**

| Tier | Route | New MCP Tool |
|------|-------|-------------|
| 1 | `/api/skill-meta/[skillId]` | `skill-meta` (new) |
| 1 | `/api/activity/summary` | `get-activity-summary` (new) |
| 1 | `/api/tabs/customize` | `customize-tabs` (new) |
| 1 | `/api/files/create` | `file-write` (existing) |
| 1 | `/api/files/delete` | `file-delete` (new — must create in core) |
| 1 | `/api/files/info` | `file-info` (existing) |
| 2 | `/api/agents/wizard/import/analyze` | `agent-analyze-import` (new) |
| 2 | `/api/agents/wizard/import/apply` | `agent-apply-import` (new) |
| 2 | `/api/agents/wizard/sources/upload` | `agent-upload-source` (new) |
| 2 | `/api/coverage` | `get-coverage-history` (new) |
| 2 | `/api/system/client-errors` | `log-client-error` (new) |
| 3 | `smb-client-template/.../assets/route.ts` | `list-template-assets` (new) |
| 3 | `workflows/.../route.ts` | `list-workflows` (new) |

**Exempt routes (binary/SSE streaming — ADR-266):**

| Route | Reason | Marker |
|-------|--------|--------|
| `apple/.../screenshots/image/route.ts` | Binary image serving | `// @fs-exempt: binary-streaming (ADR-266)` |
| `apple/.../notes/events/route.ts` | SSE polling | `// @fs-exempt: sse-streaming (ADR-266)` |
| `debug/.../send-to-agent/route.ts` | Debug tooling + spawn | `// @fs-exempt: debug-tooling (ADR-266)` |

**Already MCP-wired but missing backend tools (create backend only):**

| Route toolName | Backend status |
|---------------|---------------|
| `list-factory-templates` | Create Python tool |
| `report-self-heal-event` | Create Python tool |

### Component C: Prevention Gates

**Gate 1: ESLint rule** — `no-restricted-imports` for `fs`/`fs/promises`/`node:fs` in `**/api/**/route.ts`, added to `apps/dashboard/eslint.config.cjs` (flat config format).

**Gate 2: Exemption mechanism** — `// @fs-exempt: <reason>` marker with `eslint-disable-next-line`. Auto-scanner recognizes exemptions.

**Gate 3: Auto-loop scanner** (`auto-fs-bypass`) — rgrep for fs operations in route files, reports violations vs exemptions via ops protocol.

**Gate 4: CI check** — Fails build if any route.ts imports fs without `@fs-exempt` marker.

**Gate 5: CLAUDE.md update** — Rule #11 sub-bullet explicitly stating route files must never import fs.

## Consequences

### Positive

- Dashboard pages survive vault reorganization (data discovered by frontmatter, not path)
- Rule #11 enforced automatically (ESLint + CI) — violations can't merge
- Consistent error handling via MCP tool pattern
- Audit trail for all vault operations
- 3 exempt routes explicitly documented with markers

### Negative

- ~13 new MCP tools to create and maintain
- Slight indirection cost (route → MCP tool → Python → file) vs direct fs read
- Exempt routes still use fs (acceptable for binary/SSE per ADR-266)

### Neutral

- Dashboard UI unchanged — only data fetching wiring changes
- Existing MCP tools reused where possible (`file-write`, `file-info`, `file-read`, `file-list`)

## Alternatives Considered

### Alternative 1: Path registry instead of frontmatter discovery

Centralized config mapping `data_type → vault_path`. Rejected: creates another central registry (violates rule #2), and paths still break on moves.

### Alternative 2: Fix only high-priority routes

Rewire Tier 1 only, leave Tier 2-3 for later. Rejected: without prevention gates, new violations would keep appearing. The ADR covers all routes + gates together; execution can be phased.

## References

- Design spec: `docs/superpowers/specs/2026-03-19-dashboard-vault-decoupling-design.md`
- ADR-452: Content-based vault discovery for sync (scanner foundation)
- ADR-451: Ideas vault cleanup (first consumer of discovery pattern)
- ADR-266: MCP-first API exceptions (binary/SSE streaming exemptions)
- CLAUDE.md rule #11: MCP-first API

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "~13 API routes: fs imports removed, replaced with MCP tool calls"
    - "vault-data-query MCP tool: new"
    - "vault-data-list MCP tool: new"
    - "file-delete MCP tool: new (added to core infrastructure)"
  patterns_deprecated:
    - "Direct fs import in route.ts files -> use MCP tools"
    - "Hardcoded vault path resolution in routes -> use vault-data-query"
    - "Path-based dashboard data loading -> frontmatter-based discovery"
  files_affected:
    - "apps/dashboard/eslint.config.cjs"
    - "CLAUDE.md (rule #11 update)"
    - ".claude/skills/apple/scripts/sync_discover.py (extend with data_source)"
    - "src/mcp/augur_mcp/infrastructure/files.py (add file-delete)"
    - "~13 route.ts files (rewire to MCP)"
    - "~3 route.ts files (add @fs-exempt markers)"
    - "~10-20 vault .md files (add data_source frontmatter)"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-453-dashboard-vault-decoupling`

### Phase 1: Foundation
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | discovery | medium | Extend sync_discover.py with data_source field + vault-data-query/vault-data-list MCP tools | `.claude/skills/apple/scripts/sync_discover.py`, MCP registration |
| 1.2 | gates | low | Add ESLint rule to flat config + auto-fs-bypass scanner + CI check + CLAUDE.md update | `apps/dashboard/eslint.config.cjs`, new auto-command, `CLAUDE.md` |
| 1.3 | core-tools | low | Create `file-delete` MCP tool in core infrastructure | `src/mcp/augur_mcp/infrastructure/files.py` |
| 1.4 | exempt | low | Add @fs-exempt markers to 3 exempt routes | 3 route.ts files |

### Phase 2: Route Rewiring
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | tier1a | medium | Rewire skill-meta + activity/summary + tabs/customize (create MCP tools + update routes) | 3 route.ts + 3 new Python scripts |
| 2.2 | tier1b | low | Rewire files/create + files/delete + files/info (use existing MCP tools) | 3 route.ts |
| 2.3 | tier2a | medium | Rewire agents/wizard routes + coverage + client-errors (create MCP tools + update routes) | 5 route.ts + 5 new Python scripts |
| 2.4 | tier2b | low | Rewire skill-level routes: smb-client-template + workflows (create MCP tools + update routes) | 2 route.ts + 2 new Python scripts |
| 2.5 | backends | low | Create missing backend tools: list-factory-templates + report-self-heal-event | 2 new Python scripts |

### Phase 3: Data + Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontmatter | low | Add data_source/data_type frontmatter to vault files consumed by dashboard | ~10-20 vault .md files |
| 3.2 | verification | high | Run ESLint (0 violations), npm run build, spot-check pages in Chrome, verify vault-data-query returns data | All affected files |

### Completion Criteria
- [ ] All phases executed
- [ ] 0 non-exempt fs imports in route.ts files (ESLint + rg verification)
- [ ] `npm run build` passes
- [ ] vault-data-query returns correct data for known types
- [ ] All 3 exempt routes have @fs-exempt markers
- [ ] auto-fs-bypass scanner reports 0 violations, 3 exemptions
- [ ] All pre-existing tests pass
- [ ] ADR status updated to Implemented
