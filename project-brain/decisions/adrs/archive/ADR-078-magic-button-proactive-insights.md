---
status: Implemented
date: '2026-02-12'
deciders:
- Project owner
related:
- ADR-047 (chatbot polish)
- ADR-076 (AI self-healing)
- ADR-059 (MCP context focus)
hub: null
tags:
- magic
- button
- proactive
- page
- insights
superseded_by: null
---

# ADR-078: Magic Button — Proactive Page Insights

## Context

The dashboard has 15+ hub pages (career, health, finance, lifestyle, observe, control, etc.), each with unique data structures, action buttons, and workflows. Currently, improvements to these pages happen only when the user explicitly requests changes or during scheduled hardening cycles (ADR-065). There is no mechanism for the system to **proactively suggest** improvements based on how the user actually uses each page.

Pain points:
1. **Passive discovery** — Users must know what to ask for. They may not realize a page could benefit from a new data field, action button, or workflow reorganization.
2. **No usage-driven feedback loop** — The daemon monitors errors and health (ADR-076) but never analyzes *usage patterns* to surface opportunities.
3. **Manual insight generation** — Improvements are identified during retrospectives or when a developer audits pages. No automated insight pipeline exists.

The floating chat window (FloatingChat.tsx) already has a toolbar with Actions/MCP Tools, Data, and Help buttons. This is the natural location for a new "Magic" button that triggers contextual improvement analysis.

## Decision

### 1. Magic Button UI Component

Add a **Magic Button** to the FloatingChat toolbar (line ~830 in `FloatingChat.tsx`, between Help and the pathname display).

| Property | Value |
|----------|-------|
| Icon | `Wand2` (lucide-react) |
| Label | "Magic" |
| Visibility | Both operation and dev modes |
| Badge | Insight count when daemon has pending insights for current page |

**Click behavior**: Fetches the current page's context (pathname, available data files, action buttons, usage stats), constructs an improvement analysis prompt, and injects it into the chat input as a pre-filled query. The user sees the query and can edit or send immediately.

**Notification badge**: When the daemon has discovered pending insights for the current page, the button shows a small orange dot/count badge. Clicking dismisses the notification and opens the insight query.

### 2. Insight Analysis Prompt

When triggered (click or notification), the system builds a prompt by gathering:

| Context Source | Data |
|----------------|------|
| Page pathname | Current hub/tab route |
| dashboard.yaml | Existing tabs, actions, data sources |
| Data files | YAML structures under `plugins/{bundle}/{skill}/` |
| Usage stats | Page view frequency, action click counts, last visit |
| Page score | Latest hardening audit score (if available) |
| Pending insights | Any daemon-generated insights for this page |

The prompt asks the LLM to analyze the page and suggest improvements across these categories:

1. **Data structure** — Missing fields, new YAML schemas, better organization
2. **Use cases** — New workflows the page could support
3. **Action buttons** — New actions to add to dashboard.yaml
4. **Organization** — Tab restructuring, grouping, navigation improvements
5. **Workflows** — New chains or chain modifications
6. **Integration** — Cross-skill connections not yet wired

Output format: Numbered list of concrete suggestions, each with category tag, effort estimate (small/medium/large), and expected impact.

### 3. Two Trigger Paths

#### Trigger 1: User Click (Manual)

1. User clicks Magic button in chat toolbar
2. Frontend calls `GET /api/insights/context?page={pathname}` to gather page context
3. Frontend constructs improvement prompt with context
4. Prompt is injected into chat textarea (user can review/edit before sending)
5. User presses Enter → AI analyzes and responds with suggestions

#### Trigger 2: Daemon-Driven Insight (Proactive)

1. New daemon child service `insight_scanner.py` runs on a configurable schedule
2. For each board: checks usage stats → if usage below threshold, skips LLM call
3. For boards with sufficient usage: calls LLM (haiku/1-turn) with page context to generate candidate insights
4. Each insight scored 0–100 by the LLM based on value/novelty/effort ratio
5. Insights stored in `plugins/ai/daemon/insights/` per page
6. Daily: insights with score >80 are promoted to "pending" status
7. Max 1 notification per day (across all pages) to avoid spam
8. Notification includes page name and top insight preview → opens dashboard to that page
9. Magic button on that page shows badge with pending insight count
10. Clicking the badge loads the insight into chat for user review

### 4. Daemon Insight Scanner

New persistent child service in `unified_daemon.py`:

```python
"insight_scanner": {
    "script": SCRIPTS_DIR / "insight_scanner.py",
    "mode": "persistent",
    "restart_delay_seconds": 60,
    "max_restarts_per_hour": 5,
}
```

**Scanner logic** (`insight_scanner.py`):

1. **Schedule**: Configurable per board, default once per day (3:00 AM with nightly)
2. **Usage gate**: Read usage stats → if page has <5 visits in the last 7 days, skip LLM analysis. The threshold is configurable.
3. **LLM analysis**: For qualifying pages, call haiku with page context (dashboard.yaml, data schemas, usage patterns). 1-turn classification — no multi-turn reasoning needed.
4. **Insight storage**: Each insight stored as YAML entry with fields:
   - `id`: UUID
   - `page`: pathname
   - `category`: data_structure | use_case | action_button | organization | workflow | integration
   - `title`: Short description
   - `description`: Detailed suggestion
   - `score`: 0–100 (LLM-assigned)
   - `status`: candidate | pending | dismissed | accepted | implemented
   - `created_at`: ISO timestamp
   - `notified_at`: null until notification sent
5. **Promotion**: Daily sweep promotes insights with score >=80 from `candidate` → `pending`
6. **Notification**: If any insights promoted today AND no notification sent today → notify user via `NotificationService` with category `insights`, max 1/day
7. **Staleness**: Insights older than 30 days with status `candidate` are auto-archived

### 5. Usage Tracking

New lightweight usage tracking via API route:

**Endpoint**: `POST /api/usage/track`
**Payload**: `{ page: string, action?: string, timestamp: string }`

Frontend fires on:
- Page navigation (debounced, 1 event per page per 5-minute window)
- Action button clicks

**Storage**: `plugins/ai/daemon/insights/usage_stats.yaml`

```yaml
pages:
  /career:
    views_7d: 23
    views_30d: 89
    last_visit: "2026-02-12T10:30:00Z"
    action_clicks:
      scan-linkedin-jobs: 5
      generate-report: 12
  /health:
    views_7d: 3
    views_30d: 15
    last_visit: "2026-02-10T08:00:00Z"
    action_clicks: {}
```

Rolling window: stats older than 30 days are pruned during nightly maintenance.

### 6. Configuration

Add `insights` category to notification preferences:

```yaml
# plugins/ai/daemon/notifications/preferences.yaml
categories:
  insights:
    enabled: true
    channels:
      - system
    cooldown: 86400  # 24 hours — max 1 notification per day
    schedule: daily
```

Add insight scanner config:

```yaml
# plugins/ai/daemon/insights/config.yaml
enabled: true
schedule:
  default_interval_hours: 24
  per_page:
    /career: 12     # More frequent for high-usage pages
    /health: 48     # Less frequent for low-usage pages
usage_threshold:
  min_views_7d: 5   # Skip LLM if fewer than 5 views in 7 days
scoring:
  promotion_threshold: 80  # Score >= 80 promotes to pending
  max_notifications_per_day: 1
  staleness_days: 30
llm:
  model: haiku      # Cheap 1-turn classification
  max_tokens: 500
```

### 7. API Routes

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/api/insights/context?page={path}` | Gather page context for Magic prompt |
| `GET` | `/api/insights/pending?page={path}` | Get pending insights for a page (badge count) |
| `POST` | `/api/insights/dismiss` | Dismiss an insight (body: `{ id }`) |
| `POST` | `/api/insights/accept` | Mark insight as accepted (body: `{ id }`) |
| `POST` | `/api/usage/track` | Record page view or action click |

### 8. File Structure

```
plugins/observability/skills/daemon/
├── scripts/
│   ├── insight_scanner.py          # New daemon child service
│   └── ...existing...
├── dashboard/
│   └── ...existing...
plugins/ai/daemon/
├── insights/
│   ├── config.yaml                 # Scanner configuration
│   ├── usage_stats.yaml            # Page usage tracking
│   ├── insights.yaml               # All insights (candidate + pending + archived)
│   └── archive/                    # Archived old insights
├── notifications/
│   └── preferences.yaml            # Updated with insights category
src/dashboard/
├── components/
│   └── FloatingChat.tsx            # Updated: Magic button added to toolbar
├── app/api/
│   ├── insights/
│   │   ├── context/route.ts        # Page context endpoint
│   │   └── pending/route.ts        # Pending insights endpoint
│   └── usage/
│       └── track/route.ts          # Usage tracking endpoint
```

## Consequences

### Positive

- **Proactive improvement loop** — System identifies opportunities without user asking
- **Usage-driven prioritization** — LLM analysis only runs on pages the user actually uses
- **Low cost** — Haiku 1-turn calls, gated by usage threshold. Most pages will never trigger LLM
- **Non-intrusive** — Max 1 notification/day, only for high-confidence insights (score >80)
- **Builds on existing infra** — Uses notification_service.py, daemon child service pattern, dashboard.yaml context

### Negative

- **New daemon child service** — Adds to the child process count (now 8 services)
- **Usage tracking overhead** — Small per-page-view API call, but debounced to minimize impact
- **LLM cost** — Even haiku has cost; misconfigured thresholds could cause excessive API calls
- **Prompt quality dependency** — Insight quality depends heavily on how well the analysis prompt is crafted

### Neutral

- Usage tracking data doubles as analytics for understanding dashboard adoption
- Insight history provides a backlog of improvement ideas even if dismissed

## Implementation Order

```
Phase 1: Data Layer + Usage Tracking
├── Step 1: Create insight data directory and config.yaml
├── Step 2: Create usage tracking API route (/api/usage/track)
├── Step 3: Add usage tracking calls in dashboard page layouts
└── Step 4: Create insights API routes (context, pending, dismiss, accept)

Phase 2: Magic Button UI (depends on Phase 1)
├── Step 5: Add Magic button to FloatingChat toolbar
├── Step 6: Implement insight badge (pending count from API)
├── Step 7: Build prompt construction logic (gather page context → format prompt)
└── Step 8: Wire button click → prompt injection into chat textarea

Phase 3: Daemon Insight Scanner (depends on Phase 1)
├── Step 9: Create insight_scanner.py script
├── Step 10: Register in unified_daemon.py as child service
├── Step 11: Add insights category to notification preferences
└── Step 12: Implement promotion + notification logic

Phase 4: Verification
├── Step 13: Test manual Magic button flow end-to-end
├── Step 14: Test daemon insight generation with mock usage data
└── Step 15: Verify notification delivery and badge display
```

## Alternatives Considered

### Alternative 1: Sidebar Panel Instead of Chat Injection

Display insights in a dedicated sidebar panel rather than injecting into chat.

**Rejected**: This creates a separate UI paradigm disconnected from the existing AI workflow. The chat window is already the primary AI interaction surface — injecting the prompt into chat keeps the user in the familiar flow and allows them to edit/refine the query before sending.

### Alternative 2: Scheduled Email/Slack Digest

Send a weekly digest of all page insights via email or Slack.

**Rejected**: Too disconnected from the dashboard context. The power of the Magic button is that it operates *in situ* — the user is looking at the page when they receive the suggestion. A weekly email loses this contextual relevance.

### Alternative 3: Always-On LLM Analysis (No Usage Gate)

Run insight analysis on all pages regardless of usage.

**Rejected**: Wasteful. Most pages won't have enough context change to justify daily LLM analysis. The usage gate ensures LLM budget is spent only on pages the user actively works with.

## References

- ADR-047: Chatbot polish & resilience (FloatingChat toolbar)
- ADR-076: AI self-healing (daemon child service pattern, LLM classification)
- ADR-059: MCP context focus (page-aware context gathering)
- `src/dashboard/components/FloatingChat.tsx` — Chat toolbar (lines 696–832)
- `plugins/observability/skills/daemon/scripts/unified_daemon.py` — Daemon service registry
- `plugins/observability/skills/daemon/scripts/notification_service.py` — Notification infrastructure
- `plugins/observability/skills/daemon/scripts/ai_self_healer.py` — LLM classification pattern

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-078: Magic Button — Proactive Page Insights**.

Read the full ADR: `docs/decisions/ADR-078-magic-button-proactive-insights.md`

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
4. Record the verdict:
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-078-magic-button", description="Implementing ADR-078: Magic Button — Proactive Page Insights")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-078-magic-button", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-078 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases → spawn all at once. PIPELINE phases → use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` → haiku, `medium` → sonnet, `high` → opus

### Execution Plan

**Team name**: `adr-078-magic-button`

#### Phase 1: Data Layer + Usage Tracking
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Create insight data directory structure and `config.yaml` with scanner settings (schedule, thresholds, LLM config) | `plugins/ai/daemon/insights/config.yaml`, `plugins/ai/daemon/insights/usage_stats.yaml`, `plugins/ai/daemon/insights/insights.yaml` |
| 1.2 | developer | medium | Create usage tracking API route — `POST /api/usage/track` accepts `{ page, action?, timestamp }`, debounces writes, stores in `usage_stats.yaml` with rolling 30-day window | `src/dashboard/app/api/usage/track/route.ts` |
| 1.3 | developer | medium | Create insights context API route — `GET /api/insights/context?page={path}` reads dashboard.yaml, data files, usage stats for the page and returns structured context JSON | `src/dashboard/app/api/insights/context/route.ts` |
| 1.4 | developer | medium | Create insights pending API route — `GET /api/insights/pending?page={path}` reads `insights.yaml`, filters by page and status=pending, returns count + summaries. Also `POST /api/insights/dismiss` and `POST /api/insights/accept` for status updates | `src/dashboard/app/api/insights/pending/route.ts`, `src/dashboard/app/api/insights/dismiss/route.ts`, `src/dashboard/app/api/insights/accept/route.ts` |

#### Phase 2: Magic Button UI (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Add Magic button (`Wand2` icon) to FloatingChat toolbar between Help button and pathname display. Include insight badge (orange dot with count) fetched from `/api/insights/pending`. Wire click handler to construct improvement prompt from `/api/insights/context` and inject into chat textarea. Follow existing button styling patterns (lines 700–829 of FloatingChat.tsx) | `src/dashboard/components/FloatingChat.tsx` |
| 2.2 | frontend | low | Add usage tracking calls — fire `POST /api/usage/track` on page navigation (debounced 5min per page) and action button clicks. Add to the layout or a src/lib hook | `src/dashboard/hooks/useUsageTracking.ts`, `src/dashboard/app/layout.tsx` |

#### Phase 3: Daemon Insight Scanner (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Create `insight_scanner.py` — daemon child service that reads usage stats, gates on usage threshold, calls haiku LLM with page context for qualifying pages, scores insights 0–100, stores in `insights.yaml`. Include promotion sweep (score >=80 → pending) and staleness cleanup (>30d → archive). Follow `ai_self_healer.py` patterns for daemon integration, LLM calls, and logging | `plugins/observability/skills/daemon/scripts/insight_scanner.py` |
| 3.2 | devops | low | Register `insight_scanner` in `unified_daemon.py` CHILD_SERVICES dict. Mode: persistent, restart_delay: 60s, max_restarts: 5/hr | `plugins/observability/skills/daemon/scripts/unified_daemon.py` |
| 3.3 | devops | low | Add `insights` category to notification preferences.yaml — enabled, system channel, cooldown 86400s (24h), schedule daily | `plugins/ai/daemon/notifications/preferences.yaml` |
| 3.4 | developer | medium | Wire notification in `insight_scanner.py` — after promotion sweep, if any insights promoted today AND no notification sent today, call `NotificationService.notify()` with category `insights`, message showing top insight title, and `open_url` pointing to the relevant page | `plugins/observability/skills/daemon/scripts/insight_scanner.py` |

#### Phase 4: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run `npm run build` in `src/dashboard/` — verify no TypeScript errors. Run `npm run test` — verify no test regressions |
| 4.2 | validator | low | Run `pytest tests/src/` — verify no Python test regressions |
| 4.3 | validator | low | Verify file structure matches ADR: all new files exist in correct locations, no orphaned imports |
| 4.4 | validator | low | Verify ADR intent: Magic button appears in toolbar, badge shows pending count, click injects prompt, daemon scanner registered |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`, `npm run test`)
- [ ] Magic button visible in FloatingChat toolbar with Wand2 icon
- [ ] Click gathers page context and injects prompt into chat
- [ ] Badge shows pending insight count from daemon
- [ ] Usage tracking fires on page nav and action clicks
- [ ] insight_scanner.py registered as daemon child service
- [ ] Notification preferences include insights category
- [ ] No orphaned files or broken references
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-078-magic-button-proactive-insights.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
