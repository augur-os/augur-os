---
title: 'ADR-535: Dashboard UX Hardening for Launch'
status: Implemented
date: 2026-04-06
deciders:
- gsannikov
related:
- ADR-491
- ADR-507
- ADR-511
---

# ADR-535: Dashboard UX Hardening for Launch

## Context

Augur is preparing for open-source launch (target: 2026-04-20). A UX audit revealed that while the dashboard is visually polished and feature-complete internally, a new user opening `localhost:3000` for the first time faces several friction points:

1. **No onboarding** — Browse page loads with 14 category tabs and 200+ cards but no guidance on where to start
2. **Chat panel broken** — Chat mode parsing fails (shows broken icons), minimize and close buttons do the same thing, empty state action buttons don't work, scrolling is bumpy, auto-focus and auto-save unreliable
3. **Terminal sessions lost on refresh** — No reconnect or detach support; page refresh kills active PTY sessions
4. **Hub sidebar unclear** — Hub names shown without descriptions; users must click each to discover purpose
5. **Unindexed categories show CLI commands** — Non-technical users see "Run `/search reindex`" instead of a button
6. **Activity page incomplete** — Shows "under construction" in navigation

These issues directly impact the launch success metric (inbound leads from session bookings). A developer who opens the dashboard and finds broken chat controls or no guidance will leave before reaching the booking page.

Competitive context: Cabinet (runcabinet.com) launched 2026-04-04 with a polished first-run experience (5-question onboarding wizard). While Augur's architecture is far more mature, the first-60-seconds UX must match the polish expectation.

## Decision

### Phase 1: Browse Page Onboarding (Tasks 0A, 0B, 0C, 0D)

**0A — Welcome banner on browse page**
- Files: `apps/dashboard/app/browse/` (browse page component)
- Add a dismissible banner (localStorage `augur-welcome-dismissed`) above category tabs
- Content: "Welcome to Augur — your second brain, on your machine." with links to explore skills and learn more
- Use existing shadcn/ui Alert or Card component

**0B — Hub tooltips in sidebar**
- Files: Sidebar navigation component
- Add shadcn/ui Tooltip to each hub item showing 1-line description on hover
- Descriptions sourced from hub metadata (assembled-hubs.json or SKILL.md frontmatter)

**0C — Hide incomplete Activity page**
- Files: Sidebar nav config or Activity page
- Either remove Activity from navigation or replace "under construction" with clean placeholder

**0D — Replace CLI reindex message with button**
- Files: Browse page category component
- Replace "Run `/search reindex category`" text with an action button using `useMcpMutation`

### Phase 2: Terminal Session Management (Tasks 0E, 0F)

**0E — Session reconnect**
- Files: `/apps/dashboard/app/api/cli/route.ts`, chat/terminal component
- Keep PTY alive on SSE disconnect (don't kill on stream close)
- Buffer output while detached (up to 2000 lines, 5-minute idle timeout)
- Add `reconnect` action to `/api/cli` that replays buffered output
- Client attempts reconnect on mount before starting new session

**0F — Session detach**
- Files: Same as 0E + chat panel UI
- Add `detach` action to `/api/cli` (close stream without killing PTY)
- Add Detach button/icon to chat panel header
- Show detached session indicator on dashboard load with Reconnect option
- Add `list` action to query active/detached sessions

### Phase 3: Chat Panel Fixes (Tasks 0G-0M)

**0G — Visible send button**
- Files: Chat input component
- Add Lucide SendHorizontal icon button next to keyboard hint
- Tooltip: "Send (⌘+Enter)". Disabled when input empty.

**0H — Fix or remove broken chat mode**
- Files: Chat component, ptyStreamParser
- Diagnose Tier 1 (chat bubble) parsing failure
- If fixable in < 3 hours: fix the parser confidence threshold / regex
- If not: remove chat mode toggle, default to terminal (Tier 3). Working terminal > broken chat.

**0I — Fix minimize vs close**
- Files: Chat panel header component
- Minimize (—): collapse panel, PTY keeps running
- Close (×): kill PTY session, clear history, collapse panel
- Add confirmation if active session: "End this session?" [End] [Cancel]

**0J — Fix empty state action buttons**
- Files: Chat empty state component
- Wire "List Skills", "Get Skill", "Find Skill" buttons to actually send commands
- Or replace with more useful actions: "What can you do?", "Search my knowledge", "Show system health"

**0K — Fix bumpy chat scroll**
- Files: Chat container component
- Diagnose: competing scroll triggers, layout shifts, smooth scroll during streaming
- Fix: debounce/consolidate scroll, use `behavior: 'instant'` during streaming, `overflow-anchor: auto`
- Scroll lock: manual scroll up should not be overridden by new output

**0L — Fix chat auto-focus**
- Files: Chat input component
- Focus on: page load, after send, after agent response completes, after exiting focus mode
- Use `inputRef.current?.focus()` with appropriate timing

**0M — Fix chat auto-save**
- Files: Chat session/history component
- Ensure save triggers on message add/update, debounced 1-2s
- Save on `beforeunload` and component unmount
- Restore messages, responses, and session context on page load

## Consequences

### Positive
- New users get a guided first experience — reduces bounce rate
- Chat panel becomes reliable — the primary AI interaction surface works correctly
- Terminal sessions survive page refresh — critical for long-running Claude Code sessions
- Activity page no longer confuses new users

### Negative
- ~3-4 days of dashboard work before other launch tasks can start (demo needs polished UX)
- If chat mode is removed (0H), lose the chat bubble visualization (can be re-added post-launch)
- Session reconnect adds complexity to PTY lifecycle management

### Neutral
- No architectural changes — all fixes are within existing component boundaries
- No new dependencies needed

## Implementation Order

```
Phase 1 (Day 1): Browse UX — all independent, can parallelize
  ├── 0A: Welcome banner
  ├── 0B: Hub tooltips
  ├── 0C: Activity page
  └── 0D: Reindex button

Phase 2 (Day 1-2): Terminal sessions — sequential
  ├── 0E: Session reconnect (prerequisite for 0F)
  └── 0F: Session detach

Phase 3 (Day 2-3): Chat fixes — mostly independent
  ├── 0G: Send button
  ├── 0H: Fix/remove chat mode
  ├── 0I: Minimize vs close
  ├── 0J: Empty state actions
  ├── 0K: Scroll fix
  ├── 0L: Auto-focus
  └── 0M: Auto-save
```

## Alternatives Considered

**1. Skip UX fixes, launch with current state**
Rejected: broken chat controls and no onboarding will lose potential leads within 60 seconds.

**2. Full onboarding wizard (like Cabinet's 5-question flow)**
Rejected for launch timeline: too much scope. Welcome banner + tooltips achieves 80% of the value in 10% of the effort. Can add wizard post-launch.

**3. Remove chat panel entirely, keep terminal-only**
Rejected: the chat panel with agent bubbles is a differentiator. Fix it rather than remove it.

## References

- Launch plan spec: `docs/superpowers/specs/2026-04-06-augur-launch-plan-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-06-augur-launch.md` (Task Group 0)
- Dashboard architecture: `docs/agent-topics/DASHBOARD.md`
- PTY implementation: `apps/dashboard/app/api/cli/route.ts`
