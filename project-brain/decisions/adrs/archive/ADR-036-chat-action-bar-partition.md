---
status: Implemented
date: '2026-02-03'
deciders: []
related: []
hub: null
tags:
- chat
- window
- action
- bar
- partition
superseded_by: null
---

# ADR-036: Chat Window vs Action Bar Partition Strategy

**Extends**: ADR-035 (CLI Chat Enhancements)

## Context

After ADR-034/035 introduced the FloatingChat window (terminal + action dialog), the dashboard had two overlapping interaction surfaces at the bottom of the screen:

1. **Action Bar** (bottom-center, auto-hides) — mode toggle, chains, commands, actions, data context, layout, help, dev tools
2. **FloatingChat** (bottom-right, fixed) — FAB button, CLI selector, terminal, action dialog

Both surfaces could trigger LLM actions, creating confusion about which to use. The action bar contained developer-oriented features (chains, dev tools) alongside user-facing features (commands, help).

## Decision

**Mode-Based Split** — The full action bar becomes dev-mode only. In operation mode, there is no floating bar at all. Instead:

- **Mode toggle** lives in the FloatingChat header (left of CLI selector)
- **Help** is a sidebar nav item (below Settings)
- **Actions** are accessible via FAB → chat → actions-list view

### Alternatives Considered

| Option | Description | Rejected Because |
|--------|-------------|-----------------|
| Option 1: Merge Both | Combine action bar and chat into one surface | Too complex, loses terminal focus |
| Option 3: Keep Separate | Polish both surfaces independently | Doesn't resolve the overlap confusion |
| Minimal floating bar | Separate thin bar for operation mode | Extra floating element clutters UI when chat already exists |

## Implementation

### What Each Mode Shows

| Component | Operation Mode | Dev Mode |
|-----------|---------------|----------|
| Full Action Bar (`PageActionButtons`) | Hidden | Visible (unchanged) |
| FloatingChat header | ModeToggle + CLI selector | ModeToggle + CLI selector |
| FAB + FloatingChat | Visible | Visible |
| Sidebar Help link | Visible | Visible |

### Dev-Mode Only Features

Commands, fast actions, chains, dev tools, data context, layout button — all **dev mode only** (in PageActionButtons).

### Key Design Decisions

- **ModeToggle extracted** as reusable component — used in both FloatingChat header and full action bar
- **ModeToggle in chat header** — always visible when chat is open, no separate floating bar needed
- **Help in sidebar** — permanent, discoverable location instead of floating bar
- **Actions via FAB** — UnifiedActionsFab opens chat; actions-list view shows available actions
- **Keyboard shortcut preserved** — Cmd+Shift+D works in both modes (handled by ModeToggle)

## Files Created

| File | Purpose |
|------|---------|
| `components/action-bar/ModeToggle.tsx` | Extracted mode toggle (dot + label + shortcut) |
| `components/ActionsListView.tsx` | Action list panel inside FloatingChat |

## Files Modified

| File | Change |
|------|--------|
| `components/PageActionButtons.tsx` | Early return null in operation mode; uses extracted ModeToggle |
| `components/FloatingChat.tsx` | Added ModeToggle to header; renders ActionsListView |
| `components/GlobalShell.tsx` | Removed MinimalActionBar |
| `lib/stores/chatStore.ts` | Added `'actions-list'` to ChatView type |
| `lib/navigation.ts` | Added Help nav item below Settings |
| `components/action-bar/index.ts` | Exports ModeToggle |

## Files Deleted

| File | Reason |
|------|--------|
| `components/MinimalActionBar.tsx` | No longer needed — mode toggle moved to chat header, help to sidebar |

## Consequences

### Positive
- Clear separation: dev tools in dev mode, clean UI in operation mode
- No extra floating bar in operation mode — less visual clutter
- Mode toggle always visible in chat header (both modes)
- Help permanently discoverable in sidebar
- Actions flow naturally into the chat system

### Negative
- Mode toggle only visible when chat window is open (FAB must be clicked first)
- Users must know about ⌘⇧D shortcut or open chat to switch modes
