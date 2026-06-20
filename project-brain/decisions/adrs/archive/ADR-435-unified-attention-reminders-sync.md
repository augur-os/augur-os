---
status: Implemented
date: 2026-03-17
deciders:
  - Gur Sannikov
related:
  - ADR-270
  - ADR-421
  - ADR-430
hub: admin
tags:
  - inbox
  - notifications
  - reviews
  - reminders
  - apple
  - sync
  - attention
superseded_by: null
---

# ADR-435: Unified Attention System with Apple Reminders Sync

## Context

Augur has three separate notification surfaces — Inbox (34 items from Apple Notes + desktop), Reviews/"Needs Your Attention" (316 pending, 314 high priority), and Daemon Notifications — each with its own panel, data model, and action flow. Users must check three places. Most items have an obvious action the system could take automatically. No integration with Apple Reminders means triage requires opening the dashboard.

Additionally, the current system is noisy. Of ~350 pending items, only 5-10 per day genuinely need a human decision. Expired jobs, known URL patterns, stale reviews — all have predictable resolutions.

## Decision

Merge all three notification surfaces into a single **"Attention" block** with smart auto-triage, and sync actionable items to **Apple Reminders** for phone/watch-based triage. Critical actions dispatch via daemon; everything else queues for next Claude session.

### Core Design

1. **Smart auto-triage** reduces 350+ items to 5-30 actionable ones via rule-based classification (two-stage: input classification → display tier)
2. **Unified "Attention" block** replaces InboxPreview + ReviewsPreview + daemon notifications with three sections: Critical, Needs Decision, Informational
3. **Apple Reminders push** — Critical + Needs Decision items pushed to single "Augur" Reminders list. Mark done = confirm suggestion. Add note = NLP-interpreted override. Flag = escalate. Due date = Eisenhower task.
4. **Priority-based execution** — Critical → daemon `claude -p` (immediate). Everything else → SessionStart hook (next session).
5. **Learning loop** — user overrides teach the system better defaults over time.

### Skill Ownership

New skill: `.claude/skills/attention/` (admin hub). Absorbs review registry from `channels`, inbox triage from `apple`, and notification feed from `daemon`. Apple skill retains Reminders CRUD tools — attention skill calls them for sync.

### Prerequisites

1. `apple-complete-reminder` MCP tool extended to accept `reminder_id` (not just `title`)
2. `ReviewPriority` enum extended with `CRITICAL` level
3. `remindctl` section targeting is aspirational — items differentiated by priority flag and title prefix until enhanced

### Key Behaviors

- **Mark Reminder done (no note)** → execute suggested action (approve, route, archive)
- **Mark Reminder done + note** → interpret note as override via keyword matching ("reject", "route to career", "defer to thursday") — supports Hebrew
- **Flag Reminder (!)** → escalate to critical tier in dashboard
- **Set due date** → create Eisenhower task
- **Act in dashboard** → auto-complete corresponding Reminder (reverse sync)
- **Conflict** → dashboard action always wins (higher intent signal)
- **Daemon execution failure** → new critical attention item raised, no auto-retry, max 3/hr

### Data Model

AttentionItem with `source_type` (review/inbox/notification), `tier` (critical/needs_decision/informational), `suggested_action` with confidence, `reminder_id` for sync mapping.

Two confidence scores: **routing confidence** (which skill?) and **action confidence** (what to do?) — both must be high for auto-resolve.

### API Routes (clean cutover, no aliases per Rule 14)

- `GET /api/attention/items` → `get-attention-items`
- `GET /api/attention/summary` → `get-attention-summary`
- `POST /api/attention/act` → `act-on-attention-item`
- `GET /api/attention/history` → `get-attention-history`
- `POST /api/attention/sync` → `sync-attention-reminders`
- `GET /api/attention/rules` → `configure-attention-rules`
- `GET /api/attention/sync-status` → `get-attention-sync-status`

Old `/api/inbox/*` and `/api/reviews/*` routes deleted.

### Storage (ADR-270 compliant)

All data at `~/Vault/Augur/admin/attention/` — pending items, history, sync map, learned patterns, custom keywords, pending actions (critical/session), execution log.

### Data Lifecycle

- Informational: 24h UI auto-dismiss, 7d file prune, 500 file cap
- Sync map: recoverable from Reminder notes (contain item ID)
- Rate limit: 20 items per sync cycle, oldest first
- Daemon polling: 5-min interval via existing service loop

## Consequences

### Positive

- One surface instead of three — users check one block and/or Apple Reminders
- 350+ items reduced to 5-30 actionable ones via smart auto-triage
- Triage from phone/watch without opening dashboard
- Critical actions execute immediately via daemon
- System learns from user corrections (action confidence improves over time)
- Clean API (7 unified routes replace scattered inbox/reviews/notification endpoints)

### Negative

- New skill to maintain (`.claude/skills/attention/`)
- Dependency on Apple Reminders sync reliability (remindctl fork)
- `remindctl` section targeting not yet available — items lack visual grouping until enhanced
- Clean cutover deletes old API routes — any external consumers of `/api/inbox/*` or `/api/reviews/*` break
- Daemon execution adds cost (critical items trigger `claude -p` automatically)

### Neutral

- Apple Reminders CRUD tools stay in `apple` skill (no ownership change)
- Vault data migrated from `channels/reviews/` to `admin/attention/` (one-time migration)
- Existing `raise_review()` callers updated to new API (additive: `priority: critical` option)

## Alternatives Considered

### Alternative 1: Keep Separate Panels, Add Reminders Sync

Add Reminders sync to each panel independently. Inbox items → one Reminders list. Reviews → another. Notifications → another.

**Rejected because**: Three Reminders lists is worse than three dashboard panels. The merge is the core value — one surface for everything.

### Alternative 2: Push All Items to Reminders (No Smart Filter)

Every inbox item and review becomes a Reminder regardless of actionability.

**Rejected because**: 350+ Reminders instantly. Defeats the purpose of Reminders as a clean triage surface. The noise reduction is essential.

### Alternative 3: LLM-Based Auto-Triage

Use Claude to classify and auto-resolve items instead of rule-based matching.

**Rejected because**: Adds cost per item, introduces latency, and creates a dependency on LLM availability for a notification system that should be instant and free. Keyword + pattern matching covers 90%+ of cases.

## References

- Design spec: `docs/superpowers/specs/2026-03-17-unified-attention-reminders-sync-design.md`
- ADR-270: Data Separation (vault storage model)
- ADR-421: Apple Reminders Sync (existing sync infrastructure)
- ADR-430: Plugin Distribution (attention skill packaging)

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "/api/inbox/*"
      to: "/api/attention/*"
    - from: "/api/reviews/*"
      to: "/api/attention/*"
    - from: "~/Vault/Augur/admin/channels/reviews/"
      to: "~/Vault/Augur/admin/attention/"
  apis_changed:
    - "/api/inbox/* → deleted, replaced by /api/attention/*"
    - "/api/reviews/* → deleted, replaced by /api/attention/*"
  patterns_deprecated:
    - "InboxPreview component (replaced by AttentionBlock)"
    - "ReviewsPreview component (replaced by AttentionBlock)"
    - "raise_review() without priority:critical support"
    - "Separate inbox/reviews/notification panels"
  files_affected:
    - "apps/dashboard/components/inbox/InboxPreview.tsx"
    - "apps/dashboard/components/ReviewsPreview.tsx"
    - "apps/dashboard/app/api/inbox/**"
    - "apps/dashboard/app/api/reviews/**"
    - ".claude/skills/channels/augur/lib/registry.py"
    - ".claude/skills/apple/scripts/inbox.py"
    - ".claude/skills/apple/scripts/mcp/tools_reminders.py"
    - ".claude/skills/daemon/scripts/mcp/_notifications.py"
```

## Implementation Prompt

**Team name**: `adr-435-attention`

### Phase 1: Prerequisites & Core Engine
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | prereq-reminder-tool | medium | Extend `apple-complete-reminder` MCP tool to accept `reminder_id` parameter alongside existing `title` + `list_name`. Test with existing Reminders. | `.claude/skills/apple/scripts/mcp/tools_reminders.py` |
| 1.2 | prereq-critical-priority | medium | Add `CRITICAL` to `ReviewPriority` enum. Update `raise_review()` to accept `priority="critical"`. Gate: only skills with `x-augur-attention.allow-critical: true` can use it. | `.claude/skills/channels/augur/lib/registry.py` |
| 1.3 | attention-skill | high | Create `.claude/skills/attention/` with SKILL.md, augur.yaml, directory structure. Implement `triage.py` (auto-triage engine with two-stage classification), `note_interpreter.py` (keyword + fuzzy matching with Hebrew support). | `.claude/skills/attention/` |
| 1.4 | attention-mcp | high | Implement MCP tools: `get-attention-items`, `get-attention-summary`, `act-on-attention-item`, `get-attention-history`, `configure-attention-rules`, `get-attention-sync-status`. Register in `__init__.py`. | `.claude/skills/attention/scripts/mcp/` |
| 1.5 | sync-adapter | high | Implement `sync_reminders.py` — push (create Reminders from attention items), pull (detect completions/flags/dates, interpret notes, execute actions), reverse sync (dashboard action → complete Reminder). Sync map in vault. | `.claude/skills/attention/scripts/sync_reminders.py` |

### Phase 2: Dashboard & Migration
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | attention-block | high | Create `AttentionBlock.tsx` with Critical/Needs Decision/Informational sections. Reminders sync icon. Auto-resolve counter footer. Replace InboxPreview and ReviewsPreview on overview page. | `.claude/skills/attention/augur/dashboard/` |
| 2.2 | api-routes | medium | Create `/api/attention/*` routes (7 endpoints). Delete `/api/inbox/*` and `/api/reviews/*`. Update all dashboard consumers to new routes. | `.claude/skills/attention/augur/api/`, `apps/dashboard/` |
| 2.3 | data-migration | medium | Migrate vault data: `~/Vault/Augur/admin/channels/reviews/{pending,history}/` → `~/Vault/Augur/admin/attention/{pending,history}/`. Seed `custom-keywords.yaml` with Hebrew defaults. Create `pending-actions/{critical,session}/` dirs. | Vault directories |
| 2.4 | source-integration | high | Update `channels/registry.py` `raise_review()` → `raise_attention()`. Update `apple/inbox.py` PatternDetector with action confidence. Update `daemon/_notifications.py` to feed into attention system. | `.claude/skills/channels/`, `.claude/skills/apple/`, `.claude/skills/daemon/` |
| 2.5 | daemon-sync | medium | Add `attention_sync` check to daemon service loop (5-min polling). Hook into existing `service_healer.py` poll cycle. Add critical execution path (`claude -p` dispatch with max 3/hr, failure → new critical item). | `.claude/skills/daemon/scripts/service_healer.py` |
| 2.6 | session-hook | medium | Add SessionStart hook that checks `pending-actions/session/` for approved actions. Injects "You have N approved actions" into session context. | `.claude/settings.json`, hook script |

### Phase 3: Testing & Verification
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | test-triage | medium | Test auto-resolve rules, confidence scoring, learning loop (3x override → updated default). | `.claude/skills/attention/augur/tests/` |
| 3.2 | test-sync | medium | Test push/pull cycle, note interpretation (English + Hebrew keywords), conflict resolution (dashboard wins), sync map recovery. | `.claude/skills/attention/augur/tests/` |
| 3.3 | test-execution | medium | Test critical daemon dispatch (success + failure paths, max 3/hr), session hook (pending action injection). | `.claude/skills/attention/augur/tests/` |
| 3.4 | test-ui | medium | Browser validation: AttentionBlock renders, tier sections display correctly, act buttons work, sync icon appears. `npm run build` passes. | `apps/dashboard/` |
| 3.5 | test-migration | medium | Verify old `/api/inbox/*` and `/api/reviews/*` routes return 404. Verify new `/api/attention/*` routes respond. Verify vault data migrated. | Integration tests |

### Completion Criteria
- [ ] `apple-complete-reminder` accepts `reminder_id`
- [ ] `raise_review()` supports `priority: critical` with skill opt-in gate
- [ ] Attention skill created with 7 MCP tools registered and responding
- [ ] Auto-triage classifies items into correct tiers
- [ ] Reminders push creates items in "Augur" list with correct title/priority/notes
- [ ] Mark done in Reminders → action executed in dashboard
- [ ] Note override interpreted correctly (English + Hebrew keywords)
- [ ] Flag in Reminders → escalated to critical in dashboard
- [ ] Due date in Reminders → Eisenhower task created
- [ ] Dashboard action → corresponding Reminder auto-completed
- [ ] Conflict resolution: dashboard always wins
- [ ] Critical action → daemon executes via `claude -p`
- [ ] Daemon failure → new critical attention item, no auto-retry
- [ ] Session hook shows pending approved actions
- [ ] AttentionBlock renders with all three tier sections
- [ ] Old inbox/reviews routes deleted, new attention routes live
- [ ] Vault data migrated from channels/reviews to admin/attention
- [ ] Learning loop: 3x consistent override updates default action
- [ ] `npm run build` passes
- [ ] `pytest` passes
- [ ] ADR-435 status → Implemented
