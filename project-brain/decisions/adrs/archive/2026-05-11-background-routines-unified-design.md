---
title: "Background Routines — Unified Discovery and Browse Category"
type: spec
status: draft
created: 2026-05-11
authors:
  - gsannikov
related:
  - shared-vault/skills/daemon/scripts/schedule_executor.py
  - shared-vault/skills/daemon/scripts/insight_scanner.py
  - config/system/adaptive_loops.yaml
  - apps/dashboard/lib/browse/types.ts
  - apps/dashboard/lib/browse/transforms.ts
  - shared-vault/skills/ingest/scripts/wiki_source_inventory.py
governance:
  next_step: ADR (via /adr write) → implementation plan (writing-plans)
tags:
  - daemon
  - dashboard
  - browse
  - discoverability
  - background-routines
  - mcp
---

# Background Routines — Unified Discovery and Browse Category

## 1. Problem

Augur has **two parallel scheduling systems** that don't share a view:

| System | Source of truth | Discovered by | Visible in Browse? |
|---|---|---|---|
| Per-skill schedules | `vault/{skill}/schedules/*.yaml` + `<skill>/schedules/*.yaml` | `schedule_executor.discover_schedules()` | ✅ Yes — `scheduled-executions` category |
| Daemon adaptive-loop services | `config/system/adaptive_loops.yaml: services.*` | `unified_daemon.py` (long-running services) | ❌ **No** |

Plus four other categories of autonomous triggers also invisible to Browse:

| Source kind | Where it lives | Currently visible? |
|---|---|---|
| Daemon scripts that spawn Claude/Codex/Gemini via `subprocess.run` | `shared-vault/skills/daemon/scripts/{insight_scanner, adaptive_loop_executor, ai_monitor_sidecar}.py` | ❌ No |
| macOS launchd jobs | `~/Library/LaunchAgents/com.augur.*.plist` | ❌ No |
| GitHub Actions cron workflows | `.github/workflows/*.yml` with `on.schedule:` | ❌ No |
| MCP server background tasks | (queryable via MCP server state) | ❌ No |

Symptoms (observed 2026-05-11 morning):

- User woke up to find 30%+ of their Claude 5h budget consumed overnight.
- No visible activity in Claude Code session history.
- Investigation showed `insight_scanner` (a daemon-adaptive-loop service from `adaptive_loops.yaml`) ran at 08:00 local, spawned 39 Claude Code background sessions (one per dashboard page), burned ~250K-600K tokens, produced ~117 new "pending" insights that piled onto a 2,219-entry backlog in `insights.yaml`, and surfaced 1 notification.
- User could not have found this from the dashboard: the Browse "Scheduled Executions" page shows `per-skill-schedule` entries only.

**The bug stated cleanly:** the dashboard claims to show "Scheduled Executions" but hides the half of scheduling that actually burns tokens. **You can't disable what you can't see.** CLAUDE.md rule 1: user-visible correctness first — fix the real user-facing problem.

This spec replaces the misleadingly-named `scheduled-executions` Browse category with a unified `background-routines` category covering every autonomous trigger on the machine, and surfaces estimated token cost per AI-CLI-spawning routine so the user can spot budget burners at a glance.

## 2. Goals and non-goals

### Goals

1. **One Browse category** (`background-routines`) that lists every autonomous trigger on the machine.
2. **Six discoverers** covering the six source kinds (`per-skill-schedule`, `daemon-service`, `daemon-script`, `launchd-agent`, `github-action`, `mcp-background`).
3. **Unified `Routine` schema** that abstracts over the six source kinds.
4. **Token-cost surfacing** for routines with `spawn_kind: ai-cli-spawn` — estimated tokens per run, 24h run count, est. 24h cost.
5. **New `list-routines` MCP tool** as the single Browse data source for this category.
6. **Soft migration** from `scheduled-executions` to `background-routines` (one-release alias period).
7. **View-only controls** for v1 — no pause/run-now/edit from the dashboard (those are follow-on ADRs).

### Non-goals

- Pause / resume / run-now / edit-cadence controls (deferred to follow-on ADR)
- Auto-disable suggestions ("this routine has burned 90% of your daily budget — pause?")
- Notifications when a routine starts / fails / changes cadence
- Routine dependency graphs (which routine triggers which)
- Multi-machine federation
- Reverse-engineering token cost for non-AI-CLI routines

## 3. The six source kinds

Concrete inventory of what `discover_all_routines()` finds on this machine today:

| Source kind | Discoverer | Example entries |
|---|---|---|
| `per-skill-schedule` | reuses `schedule_executor.discover_schedules()` | `auto-mcp-health-audit`, `auto-vault-hygiene`, scheduled actions per skill |
| `daemon-service` | new — reads `config/system/adaptive_loops.yaml` services | `insight_scanner`, `continuous_executor`, `mcp_health_monitor`, `dashboard_monitor`, `log_monitor`, `plugin_watcher`, `adaptive_loop_engine`, `schedule_executor`, `notification_processor` |
| `daemon-script` | new — introspects scripts that call `resolve_cli()` + `subprocess.run(claude-cli, ...)` | `insight_scanner`, `adaptive_loop_executor`, `ai_monitor_sidecar` |
| `launchd-agent` | new — parses `launchctl list \| grep augur` output | `com.augur.daemon`, `com.augur.dashboard` |
| `github-action` | new — yaml-parses `.github/workflows/*.yml` with `on.schedule:` triggers | nightly checks, dependency audits, release flows |
| `mcp-background` | new — queries MCP server for registered background tasks | empty for v1; placeholder discoverer |

A given identity can appear under multiple source kinds (e.g., `insight_scanner` is both a `daemon-service` AND a `daemon-script`). The discoverer makes that explicit — one entry per `(id, source_kind)` pair. Frontend deduplicates display by `id` and shows source-kind chips.

## 4. Unified `Routine` schema

```yaml
id: insight_scanner                              # stable identity (string)
display_name: "Insight Scanner"
source_kind: daemon-service                      # one of the 6 above
source_path: shared-vault/skills/daemon/scripts/insight_scanner.py
config_path: config/system/adaptive_loops.yaml#services.insight_scanner
cadence:
  type: interval                                 # interval | cron | event | manual | logon
  spec: "every 12h"                              # human-readable
  spec_raw: "interval_hours: 12"                 # what the config actually says
  next_run_estimated: 2026-05-11T17:00:00Z       # null if event/manual
status: enabled                                  # enabled | disabled | erroring | paused
spawn_kind: ai-cli-spawn                         # bash | python | llm-via-router | ai-cli-spawn | http-action
ai_cost:                                         # ONLY when spawn_kind = ai-cli-spawn
  cli: claude                                    # claude | codex | gemini
  estimated_tokens_per_run: 250000               # derived from log sampling (per-run timing × canonical avg)
  estimated_runs_per_day: 2                      # derived from cadence
  estimated_tokens_per_day: 500000               # = tokens_per_run × runs_per_day
last_run_at: 2026-05-11T05:08:29Z                # null if never run
last_run_status: succeeded                       # succeeded | failed | timeout | skipped
last_run_log: ~/Library/Logs/Augur/insight_scanner/2026-05-11/08-00_54126.log
recent_runs_24h: 1
description: "Scans ~39 dashboard pages every 12h and asks Claude to suggest 1-3 improvements per page. Backlog accumulates in state/daemon/insights/insights.yaml."
tags: [insight, dashboard-audit, claude-spawn]
```

### 4.1 Required vs. optional fields

| Field | Required? | Notes |
|---|---|---|
| `id` | required | Used for deduplication across multiple source kinds |
| `display_name` | required | Falls back to `id` if not provided by discoverer |
| `source_kind` | required | Enum |
| `source_path` | required | Where the runtime code lives |
| `config_path` | optional | Where the cadence config lives (often same as source_path for daemon scripts) |
| `cadence` | required | All four sub-fields required EXCEPT `next_run_estimated` (null for event/manual) |
| `status` | required | Default `enabled` if discoverer can't tell |
| `spawn_kind` | required | Enum |
| `ai_cost` | required iff `spawn_kind = ai-cli-spawn` | Discoverer responsible for deriving |
| `last_run_*` | optional | Filled in from log inspection if available |
| `recent_runs_24h` | optional | Counted from logs |
| `description` | optional | Free-text |
| `tags` | optional | Free-form labels |

### 4.2 `spawn_kind` semantics

| Value | Meaning | Cost implication |
|---|---|---|
| `bash` | Pure shell command | Free |
| `python` | Pure Python script (no LLM calls) | Free |
| `llm-via-router` | Approved direct LLM exception routed through `config/system/llm.yaml` | Only for named user-approved exceptions |
| **`ai-cli-spawn`** | **`subprocess.run([claude\|codex\|gemini, "--print", ...])` — uses your subscription credits** | **THE EXPENSIVE ONE** |
| `http-action` | POSTs to `/api/actions/{run,oneshot}` on the dashboard | Inherits the action's underlying cost |

The point of the enum is to make the cost surface unmissable. A routine with `spawn_kind: ai-cli-spawn` gets a red/amber badge in the Browse card and an `ai_cost` panel.

## 5. Discovery architecture

```python
# shared-vault/skills/daemon/scripts/routine_discovery.py (NEW MODULE)

from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Routine:
    id: str
    display_name: str
    source_kind: str
    source_path: str
    config_path: str | None
    cadence: dict
    status: str
    spawn_kind: str
    ai_cost: dict | None
    last_run_at: str | None
    last_run_status: str | None
    last_run_log: str | None
    recent_runs_24h: int | None
    description: str | None
    tags: list[str]

class RoutineDiscoverer(Protocol):
    source_kind: str
    def discover(self) -> list[Routine]: ...

DISCOVERERS: list[RoutineDiscoverer] = [
    PerSkillScheduleDiscoverer(),
    DaemonServiceDiscoverer(),
    DaemonScriptDiscoverer(),
    LaunchdAgentDiscoverer(),
    GitHubActionsDiscoverer(),
    McpBackgroundDiscoverer(),
]

def discover_all_routines() -> list[Routine]:
    routines = []
    for d in DISCOVERERS:
        try:
            routines.extend(d.discover())
        except Exception as exc:
            logger.warning("discoverer %s failed: %s", d.source_kind, exc)
    return routines
```

### 5.1 Per-discoverer rules

**`PerSkillScheduleDiscoverer`** — reuses `schedule_executor.discover_schedules()` verbatim. Maps each existing schedule dict into `Routine` shape. `spawn_kind` derived from `dispatch` field: `fire` → `http-action`, `oneshot` → `http-action`. No `ai_cost` for v1 (dispatch goes through dashboard route, not direct CLI spawn).

**`DaemonServiceDiscoverer`** — yaml-parses `config/system/adaptive_loops.yaml: services.*`. Each service entry becomes a routine. Cadence derived from `interval_hours` or `poll_interval_seconds`. `spawn_kind` defaults to `python` unless the service is known to spawn an AI CLI (see overlap with `DaemonScriptDiscoverer` below).

**`DaemonScriptDiscoverer`** — greps `shared-vault/skills/daemon/scripts/*.py` for `resolve_cli(` + `subprocess.run`. For each match: `spawn_kind: ai-cli-spawn`, populates `ai_cost` from log sampling. Today this finds: `insight_scanner`, `adaptive_loop_executor`, `ai_monitor_sidecar`.

**`LaunchdAgentDiscoverer`** — parses `~/Library/LaunchAgents/com.augur.*.plist` (XML). Extracts `Label`, `Program`, `RunAtLoad`, `StartInterval`, `StartCalendarInterval`. Cadence is `logon` for `RunAtLoad`, `interval` for `StartInterval`, `cron` for `StartCalendarInterval`.

**`GitHubActionsDiscoverer`** — yaml-parses `.github/workflows/*.yml`. For each workflow with `on.schedule.*.cron`, emits a `Routine` with `cadence.type: cron`, `cadence.spec_raw: <cron-expr>`. `spawn_kind: http-action` (runs in GH Actions, not on this machine, but it's still an autonomous trigger that affects the repo).

**`McpBackgroundDiscoverer`** — placeholder for v1. Returns empty list. Reserved for when MCP servers register background tasks; structure ready.

### 5.2 Deduplication and cross-source overlap

Some routines appear in multiple sources (e.g., `insight_scanner` is both `daemon-service` AND `daemon-script`). Browse card de-dupes by `id` and shows multiple source-kind chips. The token-cost from `daemon-script` discoverer wins when both fire.

### 5.3 AI cost derivation

For `spawn_kind: ai-cli-spawn` routines, the discoverer estimates `estimated_tokens_per_run` from log sampling:

1. Find the most recent 5 runs from `~/Library/Logs/Augur/{service}/...`.
2. For each run, count Claude Code session JSONL files created in the same window (rough proxy for spawn count).
3. Multiply by canonical avg tokens/run for `--max-turns 1 --print` Claude sessions (start with constant 10,000 tokens; calibrate later).
4. Sample-mean across the 5 runs → `estimated_tokens_per_run`.

If the discoverer can't find logs (cold start), `estimated_tokens_per_run = null` and the UI shows "—" with a tooltip explaining "no recent runs to sample." Not an error, not a fail-loud case.

## 6. New MCP tool: `list-routines`

```python
@mcp.tool(name="list-routines")
async def list_routines(
    source_kind: str = "",      # filter to one source kind, or empty for all
    spawn_kind: str = "",        # filter to one spawn kind, or empty for all
    status: str = "",            # filter to one status, or empty for all
) -> str:
    """List background routines on this machine.

    Returns the unified Routine[] list from discover_all_routines(), optionally filtered.
    """
    routines = discover_all_routines()
    if source_kind: routines = [r for r in routines if r.source_kind == source_kind]
    if spawn_kind:  routines = [r for r in routines if r.spawn_kind == spawn_kind]
    if status:      routines = [r for r in routines if r.status == status]
    return json.dumps({"success": True, "routines": [asdict(r) for r in routines]}, indent=2, default=str)
```

Cached server-side: 60s (discovery is filesystem-heavy across 6 sources). The cache invalidates on:
- `adaptive_loops.yaml` mtime change
- Any `vault/{skill}/schedules/*.yaml` mtime change
- Any `.github/workflows/*.yml` mtime change
- launchd `com.augur.*.plist` mtime change

## 7. Browse category changes

### 7.1 Rename

`apps/dashboard/lib/browse/types.ts`:

```typescript
// before
{ id: "scheduled-executions", label: "Scheduled Executions", singularLabel: "Scheduled Execution", icon: "Clock3", devOnly: false, group: "system", viewLayout: "table" }

// after
{ id: "background-routines", label: "Background Routines", singularLabel: "Routine", icon: "Activity", devOnly: false, group: "system", viewLayout: "table" }
```

`ViewMode` union: drop `"scheduled-executions"`, add `"background-routines"`. Soft alias: a redirect mapping in `useBrowseState.ts` translates `?category=scheduled-executions` → `?category=background-routines` for one release.

### 7.2 First-class UI surfaces

**`cadence` and `last_run_at` are first-class** on every UI surface (card, table, detail panel, description line). Not optional columns — every view shows when a routine fires and when it last fired, because those two answer the user's first question: "is this thing alive and how often does it cost me?"

### 7.3 Card view (when `viewLayout: card`)

Each routine card has a fixed three-row layout:

```
┌──────────────────────────────────────────────────────────────┐
│ ⚙  Insight Scanner                          [ai-cli-spawn]  │  ← Row 1: name + spawn-kind badge
│                                                              │
│ ⏱  every 12h · next: in 4h 12m · last: 5h ago               │  ← Row 2: CADENCE + LAST RUN (first-class)
│                                                              │
│ daemon-service · 250K tokens/day · enabled · succeeded       │  ← Row 3: source kind · cost · status
└──────────────────────────────────────────────────────────────┘
```

- Row 2 is the **always-rendered cadence+last-run line**. Format:
  - `⏱  <cadence.spec> · next: <next_run_human> · last: <last_run_human>`
  - For `cadence.type = event | manual`, omit "next: …"
  - For `last_run_at = null`, render "last: never"
  - For `cadence.type = cron`, replace `<cadence.spec>` with `<cadence.spec_raw>` if more human-readable
- Row 1's spawn-kind badge is red/amber for `ai-cli-spawn`, neutral for others.
- Row 3 shows cost only when `spawn_kind = ai-cli-spawn`; otherwise that segment is omitted.

### 7.4 Table view (when `viewLayout: table`, default for this category)

| Column | Source | Notes |
|---|---|---|
| Name | `routine.display_name` | Click → detail panel |
| Source kind chip(s) | `routine.source_kind` (+ from any duplicate id) | Color-coded by kind |
| **Cadence** | `routine.cadence.spec` | "every 12h" / "0 3 * * *" / "logon" — **first-class column, never collapsed on responsive** |
| **Next run** | `routine.cadence.next_run_estimated` | "in 4h 12m" / "—" if event/manual — **first-class** |
| Spawn kind | `routine.spawn_kind` | **Red/amber badge if `ai-cli-spawn`** |
| Est. tokens/day | `routine.ai_cost.estimated_tokens_per_day` | "—" if not `ai-cli-spawn` |
| Status | `routine.status` | Green dot / amber / red |
| **Last run** | `routine.last_run_at` | **"5h ago" / "never" — first-class, never collapsed** |

"First-class" means: the three cadence/run columns (Cadence, Next run, Last run) survive responsive collapse — they're the last to fall off when the table narrows. Spawn kind and Est. tokens/day collapse before them on small screens.

### 7.5 Detail panel

`apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx` is renamed to `BackgroundRoutineDetailPanel.tsx`. Layout:

```
Insight Scanner                                          [ai-cli-spawn]
─────────────────────────────────────────────────────────────────────────

CADENCE                                LAST RUN
every 12h                              5h ago (succeeded)
next: in 4h 12m                        → ~/Library/Logs/.../08-00_54126.log
spec (raw): interval_hours: 12         
                                       recent 24h: 1 run

SOURCE                                 ESTIMATED COST (last 5 runs)
daemon-service                         ~250,000 tokens / run
shared-vault/skills/daemon/scripts/    ~500,000 tokens / day
  insight_scanner.py                   ~ 30% of 5h Claude budget

CONFIG                                 STATUS
config/system/adaptive_loops.yaml      enabled
  #services.insight_scanner            
[Reveal config]                        

DESCRIPTION
Scans ~39 dashboard pages every 12h and asks Claude to suggest 1-3
improvements per page. Backlog accumulates in state/daemon/insights/
insights.yaml (2,219 entries, max 1 surfaced per day).

[View recent runs]   [Reveal source]   [Reveal config]
```

Two-column grid with **CADENCE** in the top-left and **LAST RUN** in the top-right — both immediately visible without scrolling. The ESTIMATED COST block sits below LAST RUN for routines with `spawn_kind: ai-cli-spawn` (omitted for others).

### 7.6 Transforms

`apps/dashboard/lib/browse/transforms.ts: case "scheduled-executions"` → `case "background-routines"`.

Description line (used in compact list / search results contexts):
```typescript
const human_cadence = formatCadence(routine.cadence);            // "every 12h" / "0 3 * * *" / "on logon"
const human_last_run = formatRelativeTime(routine.last_run_at);  // "5h ago" / "never"
const cost_seg = routine.ai_cost
  ? `${humanizeTokens(routine.ai_cost.estimated_tokens_per_day)}/day`
  : null;

description = [
  human_cadence,                          // 1st: cadence (always)
  `last: ${human_last_run}`,              // 2nd: last run (always)
  routine.source_kind,                     // 3rd: source kind
  cost_seg,                                // 4th: cost (only if ai-cli-spawn)
  routine.status,                          // 5th: status
].filter(Boolean).join(" · ");
```

Cadence and last-run always lead the description line — they're never pushed off by other fields.

### 7.7 Helper formatters (new module)

`apps/dashboard/lib/browse/routine-format.ts` (NEW):

```typescript
/** Format a Routine.cadence into a one-line human string. */
export function formatCadence(c: Routine["cadence"]): string {
  if (c.type === "manual" || c.type === "event") return c.spec;
  if (c.type === "logon") return "on logon";
  return c.spec;  // "every 12h" / "0 3 * * *" - already human-ready from discoverer
}

/** Format an ISO-8601 timestamp into a relative time. */
export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "never";
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000)      return "just now";
  if (diff < 3_600_000)   return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000)  return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

/** Token count → "250K" / "1.2M" */
export function humanizeTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${Math.round(n / 1_000)}K`;
  return String(n);
}
```

These three helpers are reused across the card, table, and detail panel surfaces.

## 8. Migration

### 8.1 What changes

| Surface | Before | After |
|---|---|---|
| Browse category id | `scheduled-executions` | `background-routines` |
| Browse category label | "Scheduled Executions" | "Background Routines" |
| URL | `/browse?category=scheduled-executions` | `/browse?category=background-routines` (old URL redirects for one release) |
| MCP tool serving Browse | (mixed) | `list-routines` |
| Detail panel component | `ScheduledExecutionDetailPanel.tsx` | `BackgroundRoutineDetailPanel.tsx` |
| RAG index category | `scheduled-executions` | `background-routines` (renamed in `wiki_source_inventory.py`) |
| `ScheduledExecutionDetail` interface | as-is | renamed to `Routine`; old name kept as alias for one release |

### 8.2 Migration steps in order

1. Add new `background-routines` category alongside `scheduled-executions` (both work).
2. Implement six discoverers + `list-routines` MCP.
3. Switch Browse to read from `list-routines` for `background-routines`.
4. Mark `scheduled-executions` as deprecated in code comments + release notes.
5. Add URL redirect: `?category=scheduled-executions` → `?category=background-routines`.
6. Ship release.
7. Next release: remove `scheduled-executions` references + URL redirect.

### 8.3 Backwards-compatibility shims

Per CLAUDE.md rule 14 (canonical cleanup over compatibility shims), shims have a one-release lifetime. The shim is a single URL redirect + a single type alias; both are scheduled for removal in the release immediately following this one.

## 9. Implementation order (4 checkpoints, one PR)

| # | Checkpoint | Verifiable by |
|---|---|---|
| **C1** | `Routine` dataclass + `routine_discovery.py` module + 6 discoverers + `discover_all_routines()` | pytest: each discoverer returns ≥1 valid `Routine` against fixture inputs; `discover_all_routines()` returns ≥10 entries on this machine |
| **C2** | `list-routines` MCP tool + filter args + 60s server-side cache | pytest with mocked discoverers; `aug list-routines` returns valid JSON |
| **C3** | Browse rename: `scheduled-executions` → `background-routines` in types/transforms/components + new `routine-format.ts` helpers (`formatCadence`, `formatRelativeTime`, `humanizeTokens`) + card/table/detail-panel rendering with **cadence + last-run as first-class** + token-cost surfacing | real-browser verification (rule 28): `/browse?category=background-routines` renders all 6 source kinds with ai-cli-spawn badge visible for `insight_scanner`, `adaptive_loop_executor`, `ai_monitor_sidecar`. Cadence + last-run visible on every card and as table columns that survive responsive collapse. Detail panel shows the 2-column "Cadence / Last Run" layout. |
| **C4** | URL redirect shim + RAG index category rename + release notes deprecation entry | grep: no broken references to `scheduled-executions` outside the deprecation shim; redirect tested |

## 10. Edge cases

| Case | Behavior |
|---|---|
| A discoverer raises an exception | `discover_all_routines()` logs warning, continues with other discoverers (no fail-loud across the whole list — partial results are still useful) |
| A routine appears under two source kinds | One `Routine` entry per `(id, source_kind)`. Browse de-dupes by `id`, shows multiple chips. |
| `ai_cost` cannot be derived (no logs) | `ai_cost = None`; UI shows "—" with tooltip explaining no recent runs |
| `next_run_estimated` cannot be computed (event/manual cadence) | `next_run_estimated = None`; UI shows "—" |
| The launchd plist has malformed XML | `LaunchdAgentDiscoverer` skips it, logs warning, continues |
| GitHub Actions workflow has no `on.schedule` | Not included (we only list scheduled triggers, not push/PR triggers) |
| A `daemon-script` with `subprocess.run(claude...)` is invoked transitively (not directly scheduled) | Discoverer still lists it with `cadence.type: event`; the user sees it's an AI-CLI spawner even without knowing its trigger |

## 11. Testing

- **pytest** — One test per discoverer against fixture inputs. One end-to-end test for `discover_all_routines()` aggregating mock discoverer outputs.
- **Real-machine integration** — Single test that calls `discover_all_routines()` against this user's actual machine state. Asserts ≥1 entry per source kind that EXISTS on this machine (skip kinds with no instances).
- **Real-browser verification (rule 28)** — `/browse?category=background-routines` loads to interactive state. The `insight_scanner` entry shows the red/amber ai-cli-spawn badge and an `estimated_tokens_per_day` value derived from its log history.
- **Migration verification** — Old `?category=scheduled-executions` URL redirects to new URL.
- **No automated test for token-cost accuracy** — the 10K-tokens-per-Claude-`--print` constant is a starting point; calibrate over time via observation. Honest reporting per rule 8.

## 12. Out of scope (explicit)

| Item | Why deferred |
|---|---|
| Pause / resume / run-now / edit-cadence dashboard controls | View-only is sufficient for v1; controls are a separate follow-on ADR (architecture: each source kind needs its own pause mechanism, non-trivial) |
| Auto-disable suggestions ("over budget — pause?") | Requires budget-tracking infrastructure not yet present |
| Notifications when a routine fires / fails | Daemon's `notification_processor` exists but reusing it for routine events is its own design problem |
| Routine dependency graphs | Complex; not blocking the visibility win |
| Real-time updates (server-sent events / websockets) | 60s cache is sufficient; live updates can be a follow-on |
| Refining the 10K-tokens-per-Claude-`--print` constant | Calibrate over weeks of observation, not in this PR |

## 13. Alternatives considered

| Alternative | Why rejected |
|---|---|
| **Narrow scope** — just merge `per-skill-schedule` + `daemon-service`, ignore other source kinds | User explicitly chose Broad; narrow misses the actual budget burners (`daemon-script` scripts) which are the whole reason for this design |
| **Keep `scheduled-executions` name** | Inaccurate — daemon services + launchd jobs aren't strictly "scheduled executions" (they're long-running services or event-triggered) |
| **Plugin-loader for discoverers** (vs. hardcoded `DISCOVERERS` list) | YAGNI. Six discoverers in a list is fine. Adding a 7th = one line. |
| **Server-side LLM call to estimate `ai_cost`** | Defeats the harness boundary; log sampling is accurate enough |
| **Don't surface token cost** | The whole point of unifying is to spot budget burners. Without `ai_cost`, this is "discoverability theater" — looks better, helps nothing. |
| **Controls in v1** (pause/run-now) | Each source kind needs its own pause mechanism (touch a state file vs. edit yaml vs. unload launchd); design surface too large for one PR |

## 14. References

- CLAUDE.md rule 1 — User-visible correctness; no fallbacks that leave the product worse
- CLAUDE.md rule 11 — Dashboard uses MCP, not direct local execution
- CLAUDE.md rule 14 — Prefer canonical cleanup over compatibility shims (one-release shim lifetime)
- ADR-176 — Adaptive Loop Engine (insight_scanner is one of its 9 services)
- ADR-216 — Hot-reload interval each cycle from service config (the mechanism that lets `interval_hours: 876000` take effect within the next cycle)
- ADR-723 — Augur Pages HTML Artifacts (parallel pattern: another Browse-category-driven discoverability fix)
- `docs/references/ai-client-execution-model.md` — "Trigger → AI Client Session → Agent orchestrates → MCP tools execute" (the model that makes daemon-spawned Claude sessions invisible to UI)

## 15. Governance

This brainstorming spec is the design record. After approval:

1. `/adr write` adopts this design as a numbered ADR.
2. `superpowers:writing-plans` skill produces an implementation plan against the ADR.
3. Implementation executes against the plan in one PR with the four checkpoints (§9).

Once shipped, `insight_scanner.interval_hours` can be safely restored from `876000` to a chosen non-zero value because the Browse page will surface what it actually costs.

## Self-review

- **Placeholder scan:** No TBDs, no TODOs, no vague "add error handling later."
- **Internal consistency:** §3 (6 source kinds) ↔ §4 (schema fields) ↔ §5 (6 discoverers) ↔ §7 (Browse columns) ↔ §9 (4 checkpoints). Every section references the same six kinds and same schema fields.
- **Scope check:** Broad-scope by user decision. Implementation order (4 checkpoints, one PR) is sized for one focused effort. ✓
- **Ambiguity check:** `spawn_kind` enum precisely listed; AI-cost derivation rule precise (5 most recent runs, constant 10K starting). Soft-migration window precise (one release, then remove). ✓
