---
status: Implemented
date: '2026-02-11'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- google
- workspace
- plugin
- hardening
superseded_by: null
---

# ADR-064: Google Workspace Plugin Hardening

## Context

The Google Workspace plugin (`plugins/productivity/skills/google-workspace`) was built in two phases:

1. **Phase 1 — Mock UI**: Static dashboard pages (Gmail, Calendar, Drive, Docs) with placeholder data, zero live API calls, and hardcoded `count: 0` everywhere. These pages look production-ready but render no real data.

2. **Phase 2 — Auth gate + direct API routes**: A functional auth flow was added (`GoogleAuthGate`, `useGoogleAuth`, 4 SSE/REST API routes under `/api/google-workspace/`). Two API routes (`gmail/route.ts`, `calendar/route.ts`) call `gog` CLI directly via `child_process.exec` — no input sanitization, no structured error handling, no tests.

**Current inventory**:

| Layer | Status | Gap |
|-------|--------|-----|
| **MCP tools** (`mcp/__init__.py`) | 7 tools registered (gmail-list, gmail-read, gmail-send, calendar-list, calendar-create, drive-list, drive-search, docs-read) | Missing: gmail-search, gmail-labels, calendar-delete, drive-download, drive-upload, docs-list, docs-create. No error normalization. |
| **Dashboard API routes** | 6 routes (auth/status, auth/connect, auth/credentials, install, gmail, calendar) | Gmail/Calendar routes use raw `exec` with string interpolation — potential command injection. No Drive or Docs routes. No Zod validation. |
| **Dashboard UI pages** | 5 pages (overview, gmail, calendar, drive, docs) | All data pages are static mocks. No `useEffect` fetch calls. No loading/error states for data. |
| **Tests** | 12 contract tests (`test_google_workspace_mcp.py`) | Tests only cover MCP CLI bridge contracts. Zero dashboard API tests. Zero component tests. |
| **dashboard.yaml** | Hub + 5 tabs defined | No `actions` section. No automation buttons. |
| **SKILL.md** | Minimal (27 lines) | Missing: capabilities matrix, MCP tool reference, data directory docs. |

**Key problems**:
- UI pages never call APIs — they're pure mock shells
- API routes bypass the MCP tool layer (direct `exec` instead of calling MCP tools)
- No action buttons for AI-driven automations (e.g., "extract career emails", "summarize today's calendar")
- Command injection risk in `gmail/route.ts` via unescaped `query` parameter in template literal
- No component or API route tests — only MCP CLI bridge mocks

## Decision

Harden the Google Workspace plugin to full production quality, following the established MCP app template pattern (like Apple, Career, and other mature plugins). This ADR covers four work areas:

### 1. Complete MCP Tool Coverage

Add missing MCP tools to `mcp/__init__.py`:

| Tool | Operation | Priority |
|------|-----------|----------|
| `google-gmail-search` | Full-text search with filters | P0 |
| `google-gmail-labels` | List labels/folders | P1 |
| `google-gmail-archive` | Archive a message | P1 |
| `google-gmail-trash` | Trash a message | P2 |
| `google-calendar-get` | Get single event details | P1 |
| `google-calendar-update` | Update an existing event | P1 |
| `google-calendar-delete` | Delete/cancel an event | P2 |
| `google-drive-download` | Download file content | P1 |
| `google-drive-info` | Get file metadata | P1 |
| `google-docs-list` | List recent documents | P0 |
| `google-docs-create` | Create a new document | P2 |
| `google-contacts-search` | Search contacts | P1 |

All tools follow the established pattern:
- `@mcp.tool()` with `tool_annotations` (readOnlyHint, destructiveHint, etc.)
- `@mcp_tool_interceptor` decorator
- `metrics.track_tool()` call
- CLIBridge `gog.run_or_error()` for execution
- Consistent JSON error envelope

### 2. Dashboard API Routes — Secure & Complete

**Fix existing routes**:
- `gmail/route.ts`: Replace string-interpolated `exec` with array-arg `spawn` (eliminates command injection). Add Zod schema validation for query params.
- `calendar/route.ts`: Same treatment — `spawn` + Zod validation.
- All routes: Use `getEnhancedPath()` for PATH (consistent with auth routes).

**Add missing routes**:

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/google-workspace/gmail` | GET | List/search emails (fix existing) |
| `/api/google-workspace/gmail/[id]` | GET | Read specific email |
| `/api/google-workspace/gmail/send` | POST | Send email |
| `/api/google-workspace/gmail/labels` | GET | List labels |
| `/api/google-workspace/calendar` | GET | List events (fix existing) |
| `/api/google-workspace/calendar` | POST | Create event |
| `/api/google-workspace/drive` | GET | List/search files |
| `/api/google-workspace/drive/[id]` | GET | File metadata |
| `/api/google-workspace/docs` | GET | List recent docs |
| `/api/google-workspace/docs/[id]` | GET | Read doc content |
| `/api/google-workspace/contacts` | GET | Search contacts |

**Shared patterns**:
- All routes use `spawn` with array args (no shell, no injection)
- Zod validation on all inputs
- `getEnhancedPath()` for Homebrew PATH resolution
- Structured error responses: `{ error: string, code?: string }`
- Timeout enforcement (30s default, 180s for auth flows)

### 3. Dashboard UI — Live Data Pages

Replace all mock pages with data-fetching components:

**Gmail page** (`gmail/page.tsx`):
- `useEffect` → fetch `/api/google-workspace/gmail` on mount
- Render email list with sender, subject, date, snippet
- Folder sidebar (Inbox, Starred, Sent, Archive) as filter buttons
- Search bar wired to `?q=` param
- Click email → expand/read inline
- Loading skeleton + error states

**Calendar page** (`calendar/page.tsx`):
- Fetch `/api/google-workspace/calendar` with configurable `days` param
- Render events in timeline view (grouped by day)
- "New Event" button → form modal → POST to create route
- Today/This Week/Upcoming stats from live data
- Month navigation (ChevronLeft/Right) wired to date range queries

**Drive page** (`drive/page.tsx`):
- Fetch `/api/google-workspace/drive` with folder/search params
- Render file list with name, type icon, modified date, sharing status
- Search bar wired to drive search API
- Grid/List toggle (already has UI, needs data)
- File type stats computed from response

**Docs page** (`docs/page.tsx`):
- Fetch `/api/google-workspace/docs` for recent documents
- Render doc list with title, last edited, collaborators
- "Shared with Me" section from drive API filtered to docs
- Click doc → read content inline or open in new tab

### 4. Action Buttons for AI Automation

Add `actions` section to `dashboard.yaml`:

```yaml
actions:
  - id: extract-career-emails
    label: Extract Career Emails
    description: "Find and summarize recent emails relevant to job search, interviews, and career opportunities"
    icon: Briefcase
    flow: llm
    mode: ide

  - id: summarize-today
    label: Summarize Today
    description: "AI summary of today's emails and calendar events"
    icon: Sparkles
    flow: llm
    mode: ide

  - id: draft-reply
    label: Draft Reply
    description: "Generate a reply draft for the selected email"
    icon: Reply
    flow: llm
    mode: ide

  - id: schedule-follow-up
    label: Schedule Follow-up
    description: "Create a calendar event to follow up on a conversation"
    icon: CalendarPlus
    flow: llm
    mode: ide

  - id: email-digest
    label: Weekly Email Digest
    description: "Generate a digest of important emails from the past week"
    icon: FileBarChart
    flow: llm
    mode: ide
```

These action buttons follow the central AI integration pattern (ADR-compliant `flow: llm` + `mode: ide`). They do NOT embed custom LLM calls — they open IDE chat with context from the MCP tools.

### 5. Testing

**MCP tool tests** (`test_google_workspace_mcp.py`):
- Add contract tests for all new MCP tools (gmail-search, gmail-labels, calendar-get, etc.)
- Add error handling tests (CLI not found, auth expired, network timeout)
- Target: 30+ contract tests covering all tools

**Dashboard API route tests** (new: `tests/dashboard/google-workspace/`):
- Test each route with mocked `gog` CLI output
- Test Zod validation rejects malformed input
- Test error responses for CLI failures
- Test command injection prevention (special chars in query params)
- Target: 20+ API route tests

**Component tests** (new: co-located `.test.tsx` files):
- `GmailPage.test.tsx`: renders loading → data → error states
- `CalendarPage.test.tsx`: renders events, date navigation
- `GoogleAuthGate.test.tsx`: renders correct step for each auth state
- Target: 15+ component tests

### 6. SKILL.md Update

Update SKILL.md with:
- Complete capabilities matrix (which services × which operations)
- Full MCP tool reference table
- API route reference
- Action button descriptions
- Data directory documentation
- Troubleshooting section (auth refresh, CLI updates)

## Consequences

### Positive
- All 4 Google Workspace services (Gmail, Calendar, Drive, Docs) become fully functional in dashboard
- Command injection vulnerability eliminated
- MCP tools provide programmatic access for agents and chains
- Action buttons enable AI-driven email triage, calendar summarization, career email extraction
- Test coverage goes from 12 contract tests to 65+ tests across MCP/API/UI layers
- Plugin reaches parity with other hardened plugins (Apple, Career)

### Negative
- Significant implementation effort (~15 files modified/created)
- Depends on `gog` CLI supporting all assumed subcommands (some may need upstream PRs)
- Live API calls require active Google OAuth — pages will show auth gate for unauthenticated users

### Neutral
- Auth flow (GoogleAuthGate + SSE streaming) is already production-quality — no changes needed
- MCP tool registration pattern is well-established — this follows existing conventions
- Dashboard API routes are in `src/dashboard/app/api/` (not plugin-mounted) per existing pattern

## Alternatives Considered

### Alternative 1: Google API Direct (no gog CLI)

Use Google's Node.js client libraries directly instead of wrapping the `gog` CLI.

**Rejected because**: The local-first architecture (ADR-006) favors CLI tools over embedded API clients. `gog` manages OAuth token refresh, credential storage in system keychain, and multi-account support — reimplementing this adds complexity. The CLI bridge pattern is proven across other plugins.

### Alternative 2: Incremental per-service hardening

Harden one service at a time (Gmail first, then Calendar, etc.) across multiple ADRs.

**Rejected because**: The services share patterns (API route structure, data fetching hooks, Zod schemas). Implementing all four together allows src/lib utilities and avoids repeated boilerplate commits. The scope is manageable in a single ADR (~15 files).

### Alternative 3: Mock data mode as fallback

Keep mock data pages as a fallback when `gog` is not authenticated.

**Rejected because**: The `GoogleAuthGate` component already handles the unauthenticated state elegantly — it blocks rendering and guides the user through setup. Adding a mock fallback creates two code paths to maintain with no real benefit.

## References

- ADR-006: Local-first architecture
- ADR-018: Plugin self-containment
- ADR-040: Portable plugin template standard
- ADR-049: Zero-technical onboarding (macOS first)
- ADR-052: Full-stack debugging vision
- ADR-063: MCP implementation hardening
- Plugin: `plugins/productivity/skills/google-workspace/`
- CLI: `gog` — https://github.com/nicholasgasior/gog
- Related commit: `23920c0e` (automated in-browser auth gate with SSE streaming)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-064-google-workspace-hardening`

### Phase 1: MCP Tools & Tests (Backend)
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add 12 new MCP tools (gmail-search, gmail-labels, gmail-archive, gmail-trash, calendar-get, calendar-update, calendar-delete, drive-download, drive-info, docs-list, docs-create, contacts-search) to register_tools() | `plugins/productivity/skills/google-workspace/mcp/__init__.py` |
| 1.2 | developer | medium | Add contract tests for all new MCP tools + error handling tests | `plugins/productivity/skills/google-workspace/tests/test_google_workspace_mcp.py` |

### Phase 2: Dashboard API Routes
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Fix gmail/route.ts — replace exec with spawn, add Zod validation, use getEnhancedPath(). Fix calendar/route.ts same treatment. | `src/dashboard/app/api/google-workspace/gmail/route.ts`, `src/dashboard/app/api/google-workspace/calendar/route.ts` |
| 2.2 | developer | medium | Create new API routes: gmail/[id], gmail/send, gmail/labels, calendar POST, drive, drive/[id], docs, docs/[id], contacts | `src/dashboard/app/api/google-workspace/` (10 new route files) |
| 2.3 | developer | low | Create API route tests with mocked gog output, Zod validation tests, injection prevention tests | `tests/dashboard/google-workspace/` |

### Phase 3: Dashboard UI Pages
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Rewrite Gmail page — live data fetch, email list, folder filters, search, read inline, loading/error states | `plugins/productivity/skills/google-workspace/augur/gmail/page.tsx` |
| 3.2 | frontend | medium | Rewrite Calendar page — live event fetch, timeline view, new event form, date navigation | `plugins/productivity/skills/google-workspace/augur/calendar/page.tsx` |
| 3.3 | frontend | medium | Rewrite Drive page — live file fetch, search, grid/list, file stats | `plugins/productivity/skills/google-workspace/augur/drive/page.tsx` |
| 3.4 | frontend | medium | Rewrite Docs page — live doc list, recent/src/lib sections, read inline | `plugins/productivity/skills/google-workspace/augur/docs/page.tsx` |

### Phase 4: Actions, Config & Docs
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Add actions section to dashboard.yaml (5 action buttons) | `plugins/productivity/skills/google-workspace/augur.yaml` |
| 4.2 | developer | low | Update SKILL.md with capabilities matrix, MCP tool reference, API routes, actions, troubleshooting | `plugins/productivity/skills/google-workspace/SKILL.md` |
| 4.3 | frontend | low | Add component tests for Gmail, Calendar, GoogleAuthGate | `plugins/productivity/skills/google-workspace/augur/*.test.tsx` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `pytest plugins/productivity/skills/google-workspace/tests/ -v` — all MCP contract tests pass |
| V.2 | validator | low | Run `npm run build` in `src/dashboard/` — no TypeScript errors |
| V.3 | validator | low | Run `npm run test` in `src/dashboard/` — all component tests pass |
| V.4 | validator | low | Run `npm run lint` — no lint errors in modified files |
| V.5 | architect | low | Verify ADR-064 intent matches implementation: all 4 services have live data, no mock shells remain, action buttons defined |

### Completion Criteria
- [ ] All 19 MCP tools registered and tested (7 existing + 12 new)
- [ ] All API routes use `spawn` with array args (no `exec`, no string interpolation)
- [ ] All 4 data pages fetch and render live data from API routes
- [ ] 5 action buttons defined in dashboard.yaml
- [ ] 65+ tests across MCP/API/UI layers
- [ ] `npm run build` passes
- [ ] `npm run lint` passes
- [ ] SKILL.md updated with full reference
- [ ] No command injection vectors remain
- [ ] ADR status updated to Accepted
