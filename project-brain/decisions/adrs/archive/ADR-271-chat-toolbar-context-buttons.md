---
status: Implemented
date: '2026-03-11'
deciders:
- User
- Claude
related: []
hub: null
tags:
- chat
- toolbar
- context
- buttons
superseded_by: null
---

# ADR-271: Chat Toolbar Context Buttons

**Design Spec**: `docs/superpowers/specs/2026-03-11-chat-toolbar-context-buttons-design.md`

## Context

The chat window toolbar has grown organically into a mode-split set of 5-6 buttons with inconsistent visibility rules. Operation mode shows Assets, Actions, Help. Dev mode shows Commands, MCP Tools, Data Browser, Magic, Help. This creates a fragmented experience where users must learn two different toolbar layouts, and the button naming does not clearly communicate what each surfaces.

ADR-270 restructures where data lives (vault, documents, state, cache, RAG), making the current Assets Browser's single-directory model obsolete — it only scans `augur/data/` and knows nothing about the vault or documents directories.

The toolbar needs to be redesigned around the ADR-270 layer separation with a consistent button set that works across both modes.

## Decision

Replace the mode-split toolbar with **4 unified buttons** visible in both operation and dev modes:

### D1: Four-Button Toolbar

```
[ Context ]  [ Actions ]  [ Search ]  [ Assist ]
```

- **Context** — Browse data and reference material for the current page (replaces Assets Browser + Data Browser)
- **Actions** — Discover and execute actions, MCP tools, and commands (replaces MCP Tools/Actions + Commands + Magic)
- **Search** — Find knowledge, files, decisions, and logs across the system (new)
- **Assist** — Get help with the current page (replaces Help)

Panels are mutually exclusive — opening one closes any other open panel.

### D2: Tab-Based Panel Layout

Both Context and Actions panels use horizontal tabs for content grouping, providing a consistent interaction pattern.

**Context tabs** (all modes): Vault | Documents | Assets | Docs
**Context tabs** (dev mode): adds Runtime tab (amber badge)

**Actions tabs** (all modes): Actions | MCP Tools
**Actions tabs** (dev mode): adds Slash Commands tab (amber badge)

### D3: Page-Scoped Filtering with Hub Expansion

All panels filter content to the current page's skill by default, with a "More from {hub}" expandable section showing sibling skills from the same hub. Search scope starts at current skill with an "Expand to all" toggle.

### D4: Unified Search Across Tabs

Both Context and Actions panels provide a single search bar that filters across all tabs simultaneously. Results show type badges. This is distinct from the Search button — panel search filters file names; the Search button queries RAG/knowledge content.

### D5: File Interaction via Context Menu

Clicking a file in Context or Search panels attaches it to the chat as context (default action). Right-click or long-press opens a context menu: Attach, Preview inline, Open in Finder, Copy path. This requires a new `FileContextMenu` component.

### D6: Magic Button Relocation

The Magic ("Analyze Page") button moves inside the Actions panel as a pinned item at the top of the Actions tab. Remains dev-mode only. Pending insights badge appears on both the outer Actions toolbar button (amber dot) and the pinned item (full count).

### D7: Context Panel Reference Section

Every tab in the Context panel includes a pinned "Reference" section below the file list, showing SKILL.md (from `plugins/{bundle}/skills/{skill}/SKILL.md`) and README.md (from `plugins/{bundle}/skills/{skill}/augur/README.md`).

### D8: New Context Files API Endpoint

A new `/api/context/files?page={pathname}&tab={vault|documents|assets|docs|runtime}` endpoint replaces `/api/assets/relevant`. It resolves the current page to a skill/bundle pair, then scans the appropriate directory tree per tab using platform-aware path functions (`get_vault_dir()`, `get_documents_dir()`, `get_state_dir()`, `get_cache_dir()`, `get_rag_dir()`).

## Consequences

### Positive

- Consistent 4-button toolbar in both modes — no more learning two layouts
- ADR-270 layer separation reflected in Context tabs (vault, documents, assets, runtime)
- Page-scoped filtering reduces noise — users see what's relevant
- Search button gives direct access to RAG knowledge without slash commands
- Magic badge on Actions button surfaces daemon insights without a dedicated button

### Negative

- New `FileContextMenu` component is new UI infrastructure with no existing precedent
- New `/api/context/files` endpoint is significant backend work — must resolve paths across 5 directory trees
- Users accustomed to the current button layout will need to relearn (mitigated by clearer naming)

### Neutral

- Assist button is a rename only — no behavior change to HelpRequestModal
- Dev-only tabs use amber badge convention already established in the codebase

## Alternatives Considered

### Alternative 1: Keep Mode-Split Buttons

Keep separate button sets for operation and dev mode. Rejected because it fragments the experience and makes the toolbar unpredictable across mode switches.

### Alternative 2: Three Buttons (No Search)

Merge search into the Context panel's search bar. Rejected because the intent is fundamentally different — browsing known files vs. querying knowledge — and a unified search bar would conflate file filtering with RAG content search.

### Alternative 3: Accordion Layout for Panels

Use collapsible accordion sections instead of tabs. Rejected in favor of tabs for consistency and the ability to show one focused group at a time with more vertical space.

### Alternative 4: Flat List with Section Headers

Single scrollable list with type headers instead of tabs. Rejected because it requires scrolling past irrelevant groups and doesn't scale well when dev mode adds more items.

## References

- Design spec: `docs/superpowers/specs/2026-03-11-chat-toolbar-context-buttons-design.md`
- ADR-270: Folder restructure and layer separation
- ADR-157: Chat CLI continuous session (created the original Assets button)
- ADR-047: Operation mode chatbot experience
- Current implementation: `src/dashboard/components/chat/ChatToolbar.tsx`, `ChatInput.tsx`

## Impact Manifest

```yaml
impact:
  patterns_deprecated:
    - grep: "AssetsBrowserControl"
      replacement: "ContextButton with tab-based panel"
    - grep: "DataBrowserControl"
      replacement: "ContextButton Assets tab"
    - grep: "CommandsControl"
      replacement: "ActionsButton Slash Commands tab"
    - grep: "MagicButton"
      replacement: "Pinned Analyze Page item in ActionsButton panel"
  apis_changed:
    - function: "/api/assets/relevant"
      module: "src/dashboard/app/api/assets/relevant/route.ts"
      breaking: true  # replaced by /api/context/files
  files_affected:
    - glob: "src/dashboard/components/chat/ChatToolbar.tsx"
    - glob: "src/dashboard/components/chat/ChatInput.tsx"
    - glob: "src/dashboard/components/chat/ChatLayout.tsx"
    - glob: "src/dashboard/components/FloatingChat.tsx"
```

## Implementation Prompt

**Team name**: `adr-271-chat-toolbar`

### Phase 1: Shared Components
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | frontend | medium | Create `TabPanel` component — horizontal tabs, active state, amber dev badge, unified search bar | `src/dashboard/components/chat/TabPanel.tsx` |
| 1.2 | frontend | medium | Create `PageScopedList` component — skill-first listing with "More from {hub}" expandable section | `src/dashboard/components/chat/PageScopedList.tsx` |
| 1.3 | frontend | medium | Create `FileContextMenu` component — right-click menu with Attach, Preview, Open, Copy path | `src/dashboard/components/chat/FileContextMenu.tsx` |

### Phase 2: Backend API
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | backend | medium | Create `/api/context/files` endpoint — resolve page to skill/bundle, scan directory per tab param, return file metadata | `src/dashboard/app/api/context/files/route.ts` |
| 2.2 | backend | low | Adapt `/api/mcp/tools/list` to support hub-expansion query param for sibling skill tools | `src/dashboard/app/api/mcp/tools/list/route.ts` |

### Phase 3: Button Components
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | high | Build `ContextButton` — tabs (Vault/Documents/Assets/Docs/Runtime), file listing via `/api/context/files`, pinned Reference section, FileContextMenu integration | `src/dashboard/components/chat/ContextButton.tsx` |
| 3.2 | frontend | high | Build `ActionsButton` — tabs (Actions/MCP Tools/Slash Commands), unified search, pinned Analyze Page item (dev only), pending insights badge | `src/dashboard/components/chat/ActionsButton.tsx` |
| 3.3 | frontend | medium | Build `SearchButton` — scope toggle, RAG search via `search-skill-knowledge` MCP, result grouping, FileContextMenu for results | `src/dashboard/components/chat/SearchButton.tsx` |
| 3.4 | frontend | low | Build `AssistButton` — rename Help to Assist, preserve HelpRequestModal behavior | `src/dashboard/components/chat/AssistButton.tsx` |

### Phase 4: Integration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | frontend | high | Rewire `ChatInput.tsx` — replace 5-6 button slots with 4 unified slots, add mutual-exclusion panel state | `src/dashboard/components/chat/ChatInput.tsx` |
| 4.2 | frontend | medium | Update `ChatLayout.tsx` and `FloatingChat.tsx` — remove old button props (magicClick, commandsControls, assetsControls, dataControls), wire new button components | `src/dashboard/components/chat/ChatLayout.tsx`, `src/dashboard/components/FloatingChat.tsx` |
| 4.3 | frontend | low | Remove deprecated components — `AssetsBrowserControl`, `DataBrowserControl`, `CommandsControl`, standalone `MagicButton` from ChatToolbar.tsx | `src/dashboard/components/chat/ChatToolbar.tsx` |

### Phase 5: Cleanup
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | backend | low | Remove `/api/assets/relevant` endpoint (replaced by `/api/context/files`) | `src/dashboard/app/api/assets/relevant/route.ts` |
| 5.2 | frontend | low | Remove `AssetsBrowser.tsx` component (functionality absorbed by ContextButton) | `src/dashboard/components/chat/AssetsBrowser.tsx` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `npm run build` in `src/dashboard/`, verify no TypeScript errors |
| V.2 | validator | low | Run existing chat component tests, verify no regressions |
| V.3 | validator | medium | Browser validation — open chat on 3 different hub pages, verify all 4 buttons render, panels open/close correctly, files list, actions list |
| V.4 | architect | low | Verify ADR intent — all 6 current buttons mapped to new 4-button design, no functionality lost |

### Completion Criteria
- [ ] All 5 phases executed
- [ ] `npm run build` passes
- [ ] All 4 buttons render in both operation and dev modes
- [ ] Context panel shows files from vault, documents, assets, docs directories
- [ ] Actions panel shows actions, MCP tools, and slash commands (dev)
- [ ] Search panel queries RAG and returns grouped results
- [ ] Assist opens HelpRequestModal
- [ ] Panels are mutually exclusive
- [ ] Dev-only tabs show amber badge
- [ ] Page filtering shows current skill first with hub expansion
- [ ] No orphaned components or API routes

## Testing

| Test Case | Type | Description |
|-----------|------|-------------|
| T1 | Component | TabPanel renders tabs, switches active tab, shows amber badge for dev tabs |
| T2 | Component | PageScopedList shows skill items first, expands hub siblings |
| T3 | Component | FileContextMenu shows on right-click with all 4 options |
| T4 | API | `/api/context/files?tab=vault` returns vault files for resolved skill |
| T5 | API | `/api/context/files?tab=runtime` returns 403 in operation mode |
| T6 | Integration | Opening Context panel closes Actions panel (mutual exclusion) |
| T7 | Integration | Search starts scoped to skill, "Expand to all" toggle searches globally |
| T8 | Integration | Clicking file in Context attaches it as chat context chip |
| T9 | Integration | Analyze Page item visible in dev mode only, hidden in operation mode |
| T10 | E2E | All 4 buttons visible on hub page in both modes |
