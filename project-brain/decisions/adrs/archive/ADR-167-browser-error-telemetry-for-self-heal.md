---
status: Implemented
date: '2026-02-26'
deciders:
- Project lead
related:
- ADR-076 (Daemon AI Self-Healing)
- ADR-084 (Unix Fail-Fast Self-Heal)
- ADR-080 (Calendar Hydration Fix)
hub: null
tags:
- browser
- error
- telemetry
- self
- heal
superseded_by: null
---

# ADR-167: Browser Error Telemetry for Self-Heal

## Context

The self-heal daemon (ADR-076) scans **server-side logs** — Python tracebacks, MCP stderr, process crashes, chain telemetry, offload failures. It catches errors that produce log files in `runtime/logs/`.

Three categories of dashboard bugs are invisible to self-heal because they only manifest in the **browser**:

1. **Hydration mismatches** — Server renders HTML with one set of data (e.g., nav items for `mode='operation'`), client re-renders with different data (e.g., `mode='development'` from localStorage). React logs `console.error("Hydration failed...")` but this never reaches any server log file. These bugs are introduced by any Zustand store, localStorage read, or time-dependent value used during initial render.

2. **Runtime errors** — `fetch()` failures from broken API routes, MCP tools that don't resolve, unhandled promise rejections, TypeError from undefined properties in API responses. These produce `console.error` in the browser and sometimes a red error overlay, but the self-heal daemon only sees the server side (if it logs to stderr at all).

3. **Component crashes** — A React component throws during render (e.g., `.map()` on undefined data). Error boundaries catch it and render fallback UI. The user sees a broken section. The daemon sees nothing — no process crash, no stderr, no log entry.

**Current scan coverage**:

| Source | Scanned | Format |
|--------|---------|--------|
| `runtime/logs/*.log` | Yes | Python logging |
| `runtime/logs/*.stderr.log` | Yes | Daemon child stderr |
| `runtime/chain_telemetry.jsonl` | Yes | Chain failures |
| `runtime/self_heal_events.jsonl` | Yes | Fail-fast emissions |
| `runtime/logs/dashboard.stderr.log` | Yes | Next.js process crashes |
| Browser `console.error` | **No** | — |
| Browser `window.onerror` | **No** | — |
| React Error Boundary `componentDidCatch` | **No** | — |

The gap: **all three bug categories produce `console.error` in the browser, but no mechanism captures browser errors into a log file the daemon can scan.**

**Real-world impact**: The hydration mismatch in `SidebarNav.tsx` (caused by `useModeStore` reading localStorage at store creation time) was only discovered by a user manually inspecting the browser console during a demo preparation session. It had been silently breaking first-page-load rendering for every user in dev mode.

## Decision

### Component 1: Client-Side Error Reporter

Create a `'use client'` component `ClientErrorReporter` mounted once in `app/layout.tsx` (alongside existing `PerformanceTracker`, `ContextManager`, `UsageTracker`). It renders nothing (`return null`).

**On mount, it installs three capture hooks:**

1. **`console.error` interceptor** — Wraps `console.error` to also batch-report errors. Captures hydration mismatches ("Hydration failed"), React warnings, and any library that logs errors via console.

2. **`window.onerror` handler** — Catches uncaught synchronous exceptions with file, line, column, and stack trace.

3. **`window.onunhandledrejection` handler** — Catches unhandled promise rejections (failed `fetch()`, async errors).

**Deduplication and batching**:
- Errors are fingerprinted by `message + source_file + line` (truncated to first 200 chars)
- Duplicate fingerprints within a 60-second window are counted but not re-reported
- Errors are batched (max 5 per POST, max 1 POST per 5 seconds) to avoid spamming the API
- Maximum 50 unique errors per page session to prevent runaway loops

**Payload per error**:
```typescript
{
  level: 'error' | 'warning',
  message: string,          // First 500 chars of error message
  source: string,           // 'console.error' | 'window.onerror' | 'unhandledrejection'
  url: string,              // window.location.pathname (no query params)
  stack?: string,           // First 1000 chars of stack trace
  component?: string,       // React component name from error boundary (if available)
  timestamp: string,        // ISO 8601
  fingerprint: string,      // Dedup key
  count: number,            // How many times this error occurred in the batch window
}
```

### Component 2: API Route

Create `POST /api/system/client-errors` (`app/api/system/client-errors/route.ts`).

**Behavior**:
- Accepts a JSON array of error objects (max 10 per request)
- Appends each as a single JSONL line to `runtime/logs/dashboard.client.jsonl`
- Creates the file and parent directory if they don't exist
- Returns `{ success: true, accepted: N }`
- No authentication required (local-only dashboard, no external exposure)
- Rate limit: max 100 writes per minute per client (tracked by simple in-memory counter, resets each minute)

**JSONL format** (one line per error, matches existing self-heal scanner expectations):
```json
{"level":"error","message":"Hydration failed because...","source":"console.error","url":"/","stack":"at SidebarNav...","timestamp":"2026-02-26T10:30:00Z","fingerprint":"hydration-sidebarNav-59","count":1}
```

### Component 3: Self-Heal Scanner Integration

Add one scan target to `plugins/observability/skills/daemon/augur/config/self_heal.yaml`:

```yaml
# Browser-side errors captured by ClientErrorReporter (ADR-167)
- path: "runtime/logs/dashboard.client.jsonl"
  patterns:
    - "Hydration failed"
    - "Unhandled Runtime Error"
    - "TypeError"
    - "ReferenceError"
    - "Cannot read properties of"
    - "Failed to fetch"
    - "unhandledrejection"
    - "ChunkLoadError"
```

The existing ripgrep-based scanner, LLM classifier, and auto-fix pipeline handle everything from here — no changes needed to the scan loop, deduplication, classification, or fix dispatch.

**Expected severity classifications** (informational — the LLM classifier decides, but these are the expected patterns):

| Error Pattern | Expected Severity | Rationale |
|---|---|---|
| `Hydration failed` | High | Known fix pattern: find localStorage read, defer to useEffect |
| `TypeError: Cannot read properties of` | High | Null safety issue, usually 1-file fix |
| `Failed to fetch` → API 500 | Medium | Broken API route, needs investigation |
| `ChunkLoadError` | Low | Stale deployment, cleared by refresh |
| `ResizeObserver loop` | Transient | Browser noise, not actionable |

### Component 4: Error Boundary Telemetry (Enhancement to Existing Boundaries)

For any React Error Boundary component that catches errors via `componentDidCatch(error, errorInfo)`:

Add a `fetch('/api/system/client-errors', ...)` call in `componentDidCatch` with:
- `source: 'error-boundary'`
- `component: errorInfo.componentStack` (truncated to first 500 chars)
- The component name from the stack identifies exactly which section crashed

This is a one-line addition per Error Boundary, not a new component. The API route and JSONL pipeline handle the rest.

## Consequences

**Positive**:
- All three blind spots (hydration, runtime, component crashes) become visible to self-heal with zero new scanning infrastructure
- Hydration mismatches get caught on first page load, not weeks later during a demo
- Browser errors get the same LLM classification → auto-fix pipeline as server errors
- Error volume per page serves as a health metric (0 = clean, >5 = degraded)
- The `dashboard.client.jsonl` file is human-readable — `cat runtime/logs/dashboard.client.jsonl | jq .` for quick debugging

**Negative**:
- Adds one `fetch()` call per batch of errors (max 1 per 5 seconds) — negligible network overhead but non-zero
- `console.error` interception can catch library noise (React StrictMode double-renders, ResizeObserver) — the LLM classifier handles these as `transient`/`dismiss`
- JSONL file grows unbounded — needs rotation (covered by existing `max_log_age_hours: 24` config which the scanner already respects; file rotation handled by adding to the daemon's log cleanup cycle)

**Neutral**:
- No new Python dependencies — the scanner already reads JSONL via ripgrep
- No new MCP tools — the API route writes directly to the filesystem
- No dashboard UI changes — the reporter is invisible (`return null`)
- Visual regressions that don't throw errors remain undetected (requires Playwright smoke tests, out of scope)

## Implementation Order

```
Phase 1: API Route + JSONL pipeline
├── Step 1: Create POST /api/system/client-errors route
└── Step 2: Verify JSONL file is created and written correctly

Phase 2: Client-side reporter (depends on Phase 1)
├── Step 3: Create ClientErrorReporter component
├── Step 4: Mount in app/layout.tsx
└── Step 5: Verify errors are captured and POSTed

Phase 3: Self-heal integration (depends on Phase 1)
├── Step 6: Add scan target to self_heal.yaml
└── Step 7: Verify scanner picks up browser errors

Phase 4: Error boundary wiring
├── Step 8: Add telemetry to existing Error Boundary components
└── Step 9: Verify component crashes are reported

Phase 5: Verification
├── Step 10: Inject a deliberate hydration mismatch, verify it appears in JSONL
├── Step 11: Trigger a fetch error, verify it appears in JSONL
├── Step 12: Crash a component, verify Error Boundary reports it
└── Step 13: Verify self-heal scanner detects and classifies errors from JSONL
```

## Alternatives Considered

### 1. Sentry / Third-party error tracking

Use Sentry, LogRocket, or Datadog RUM for browser error capture.

**Rejected because**: Violates local-first architecture (ADR-006). Error data contains page URLs, component names, and stack traces that reveal project structure. Cloud dependency for a local-only dashboard adds latency and a failure mode. The self-heal pipeline already has classification and auto-fix — Sentry would be a parallel system with no integration.

### 2. Playwright smoke tests as the detection layer

Run Playwright against key pages on every build or on a schedule, capture console errors from the browser context.

**Rejected as primary mechanism because**: Only catches errors at test time, not during normal use. A hydration mismatch that depends on localStorage state (like the mode store bug) requires specific user state to reproduce — a clean Playwright session wouldn't trigger it. However, Playwright smoke tests are complementary and could be added later as a nightly job feeding into the same JSONL file.

### 3. Next.js `instrumentation.ts` for server-side error capture

Use Next.js instrumentation hooks to capture API route errors on the server.

**Rejected as sole solution because**: Only catches server-side errors. Hydration mismatches and component crashes are client-only. However, `instrumentation.ts` could complement this ADR for better API error coverage — the two are not mutually exclusive.

### 4. Custom Next.js error page with telemetry

Override `app/error.tsx` and `app/global-error.tsx` to report errors.

**Rejected as sole solution because**: These only trigger on unrecoverable errors that crash the entire page. Error boundaries inside components catch most errors before they bubble up. The `ClientErrorReporter` approach catches everything — console errors, unhandled rejections, and error boundary catches — not just page-level crashes.

## References

- ADR-076: Daemon AI Self-Healing (scanner, classifier, fix pipeline)
- ADR-084: Unix Fail-Fast Self-Heal (structured event emission)
- ADR-080: Calendar Hydration Fix (manual fix for a hydration bug — this ADR automates detection)
- `plugins/observability/skills/daemon/augur/config/self_heal.yaml` — Scanner config
- `plugins/observability/skills/daemon/scripts/dashboard_monitor.py` — Dashboard health monitor
- `src/dashboard/app/layout.tsx` — Root layout (mount point for reporter)
- `src/dashboard/components/PerformanceTracker.tsx` — Existing pattern for invisible client component in layout

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-167: Browser Error Telemetry for Self-Heal**.

Read the full ADR: `docs/decisions/ADR-167-browser-error-telemetry-for-self-heal.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-167-browser-telemetry", description="Implementing ADR-167: Browser Error Telemetry for Self-Heal")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-167-browser-telemetry", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-167-browser-telemetry team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-167-browser-telemetry`

#### Phase 1: API Route + JSONL Pipeline
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Create `POST /api/system/client-errors` route. Accept JSON array of error objects (max 10), append each as JSONL line to `runtime/logs/dashboard.client.jsonl`. Create file/dir if missing. Add rate limit counter (100/min). Return `{ success: true, accepted: N }` | `src/dashboard/app/api/system/client-errors/route.ts` |
| 1.2 | validator | low | POST a test payload to the route, verify JSONL file is created with correct format | — |

#### Phase 2: Client-Side Reporter (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create `ClientErrorReporter` component. On mount: (1) wrap `console.error` to intercept errors, (2) install `window.onerror` handler, (3) install `window.onunhandledrejection` handler. Deduplicate by fingerprint (message+source+line, 200 chars). Batch max 5 errors per POST, max 1 POST per 5 seconds, max 50 unique errors per session. Component renders `null`. | `src/dashboard/components/ClientErrorReporter.tsx` |
| 2.2 | developer | low | Mount `ClientErrorReporter` in `app/layout.tsx` alongside existing `PerformanceTracker` | `src/dashboard/app/layout.tsx` |
| 2.3 | validator | low | Trigger a `console.error('Test error')` in browser devtools, verify it appears in `runtime/logs/dashboard.client.jsonl` | — |

#### Phase 3: Self-Heal Integration (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Add `dashboard.client.jsonl` scan target to `self_heal.yaml` with patterns: `Hydration failed`, `Unhandled Runtime Error`, `TypeError`, `ReferenceError`, `Cannot read properties of`, `Failed to fetch`, `unhandledrejection`, `ChunkLoadError` | `plugins/observability/skills/daemon/augur/config/self_heal.yaml` |
| 3.2 | validator | low | Write a test JSONL line to the file, run the scanner, verify it detects the entry | — |

#### Phase 4: Error Boundary Wiring
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Find all Error Boundary components in `src/dashboard/` (grep for `componentDidCatch` or `ErrorBoundary`). Add a `fetch('/api/system/client-errors', ...)` call in each `componentDidCatch` with `source: 'error-boundary'` and truncated `componentStack` | Error Boundary files (discover via grep) |

#### Phase 5: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 5.1 | validator | low | Run `pytest tests/src/` — verify no regressions |
| 5.2 | validator | low | Run `npm run build` — verify dashboard build passes |
| 5.3 | validator | low | Verify JSONL file format matches self-heal scanner expectations (ripgrep pattern matching) |
| 5.4 | architect | low | Verify ADR intent matches implementation — browser errors flow through JSONL to self-heal scanner without any new scanning infrastructure |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] `POST /api/system/client-errors` writes JSONL entries
- [ ] `ClientErrorReporter` captures `console.error`, `window.onerror`, `unhandledrejection`
- [ ] `self_heal.yaml` includes `dashboard.client.jsonl` scan target
- [ ] Error Boundaries report crashes via the API
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-167-browser-error-telemetry-for-self-heal.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
