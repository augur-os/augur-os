---
status: Implemented
date: '2026-02-25'
deciders:
- Gur
related:
- ADR-114 (centralized editor settings)
- ADR-080 (Apple hardening)
- ADR-109 (filesystem-driven dashboard)
hub: null
tags:
- seamless
- note
- editing
- integration
- apple
superseded_by: null
---

# ADR-158: Seamless Note Editing Integration (Apple Notes + MarkText)

## Context

Augur currently has two note-taking paths that don't connect well:

1. **Apple Notes inbox**: Mobile capture via `apple-read-notes` MCP tool — users jot things on their phone, Augur processes them
2. **Long-form notes**: Markdown files in skill data directories, opened in external editors (MarkText, iA Writer) via `system-open`

But there's no reverse path: Augur-managed content can't flow *back* to Apple Notes for mobile access, and Apple Notes inbox items can't be promoted to proper markdown files without manual copy-paste.

The gap: **two disconnected islands** (Apple Notes inbox, local markdown files) with no automated sync or promotion path between them.

### Constraints

- Augur is local-first — no cloud editor, no SaaS dependency
- ADR-114 already established per-extension editor routing (`file_editors` in preferences.yaml)
- Apple Notes MCP tools exist: `apple-read-notes`, `apple-create-note`, `apple-update-note`
- Apple Notes API uses osascript with 30s timeout — slow for bulk operations, synchronous/blocking
- MarkText is the preferred markdown editor (via ADR-114 routing)
- Existing daemon infrastructure is Python-based (daemon skill in plugins/admin)
- Building a full rich-text editor is explicitly out of scope (see architecture discussion — this is undifferentiated infrastructure)
- The AI orchestration layer is where editing value should come from, not the editor surface

## Decision

Implement a **three-tier note lifecycle** with seamless transitions between tiers, using Apple Notes as mobile capture, local markdown as the canonical store, and external editors for rich editing. The AI layer handles all promotion/demotion/sync logic.

### Tier 1: Quick Capture (Apple Notes → Augur Inbox)

**What exists**: Apple Notes inbox pattern (`📥 Inbox` note, skill-specific inbox notes)
**What's new**:

- **Auto-ingest daemon**: Periodic poll (every 5 min) that reads Apple Notes inbox via `apple-read-notes`, extracts new items, and creates local markdown files in the appropriate skill's data directory. Runs as a Python daemon task (consistent with existing daemon infrastructure). Includes a circuit breaker: skip poll if previous poll hasn't completed, to avoid accumulating blocked osascript calls under load
- **Structured extraction**: AI parses each inbox item to determine: target skill, content type (note, task, idea, link), priority, and tags
- **Receipt confirmation**: After successful ingestion, move item to ✅ PROCESSED section in Apple Notes (existing pattern)
- **Mobile-friendly format**: Apple Notes inbox keeps its current simple format — users just type below the 📥 line

### Tier 2: Local Markdown (Canonical Store)

**What exists**: Markdown files in skill data directories, opened via `system-open` with editor resolution
**What's new**:

- **Standardized note structure** per skill:
  ```
  plugins/{bundle}/skills/{skill}/augur/data/notes/
  ├── {date}-{slug}.md          # Individual notes (frontmatter is source of truth)
  ├── _index.cache.yaml         # Derived cache — regenerated from frontmatter on scan
  └── _templates/                # Per-skill note templates
  ```
  Note: `_index.cache.yaml` is a **derived artifact**, not authoritative. It is rebuilt by scanning `*.md` frontmatter and exists only for fast listing without re-parsing all files. On any conflict, frontmatter wins.
- **One-click edit**: Dashboard "Edit" button calls `system-open` with MarkText (or configured editor per ADR-114). File watcher detects save → auto-refresh dashboard view
- **Frontmatter convention**:
  ```yaml
  ---
  title: "Meeting Notes: Q1 Review"
  created: 2026-02-25T10:00:00+02:00
  source: apple-notes    # or "manual" or "ai-generated"
  skill: career
  tags: [meeting, quarterly]
  sync_to_apple: true     # Flag for reverse sync
  ---
  ```
- **Filesystem watcher**: Python `watchdog` library on notes directories (consistent with Python daemon infrastructure — no new Node.js long-running process). On file change → rebuild `_index.cache.yaml`, notify dashboard via SSE, optionally trigger reverse sync to Apple Notes if `sync_to_apple: true` in frontmatter. Debounced at 2s to coalesce rapid saves

### Tier 3: AI-Powered Note Operations (The Differentiator)

Instead of building an editor, make the AI layer the power tool. Commands follow the existing `/verb-noun` pattern (not subcommands):

- **`/note-create`**: Chat command that creates a note from conversation context, places it in the right skill directory, opens in editor
- **`/note-promote`**: Takes an Apple Notes inbox item and expands it into a full structured markdown note (AI determines skill, generates frontmatter, adds structure around user's raw content)
- **`/note-summarize`**: Takes a long markdown note and creates a condensed version or extracts key points
- **`/note-sync`**: Pushes a local markdown note to Apple Notes for mobile access (stripped to plain text, preserving structure)
- **`/note-search`**: RAG-powered search across all notes (already exists via knowledge skill, but surfaced as a note-specific command)
- **`/note-merge`**: Combines related notes from different skills into a single document

### Reverse Sync: Augur → Apple Notes

- When `sync_to_apple: true` in frontmatter, changes to the local markdown file trigger an `apple-update-note` call
- Markdown is converted to Apple Notes-compatible format (plain text with basic structure preserved)
- A "mirror note" is created/updated in Apple Notes with a header: `🔄 Synced from Augur | {skill} | Last: {timestamp} | DO NOT EDIT HERE`
- This is **one-way push** (Augur → Apple Notes), not bidirectional sync. Apple Notes inbox remains the capture path; synced notes are read-only mirrors for mobile access
- **Conflict handling**: Last-write-wins semantics. A per-note sync lock prevents overlapping `apple-update-note` calls from rapid saves. If osascript fails mid-update, the sync is retried once on the next watcher cycle; persistent failures log a warning and set `sync_status: failed` in the cache
- **User edits to mirrors are overwritten** on next sync — the "DO NOT EDIT HERE" header makes this explicit

### Integration Points

| Component | Role | Protocol |
|-----------|------|----------|
| Apple Notes MCP | Mobile capture + read-only mirror | `apple-read-notes`, `apple-create-note`, `apple-update-note` |
| MarkText | Rich markdown editing | `system-open` via ADR-114 editor resolution |
| Filesystem watcher | Change detection on `.md` files | Python `watchdog` in daemon → SSE to dashboard |
| Auto-ingest daemon | Periodic Apple Notes polling | Python daemon task (5 min interval, circuit breaker) |
| AI orchestration | Promotion, summarization, sync, search | MCP tools + slash commands |
| RAG index | Search across all notes | Existing knowledge skill (verify `notes/` paths are indexed) |

### Configuration

Extend `preferences.yaml` (user preferences):
```yaml
file_editors:
  md: "MarkText"

notes:
  default_sync_to_apple: false   # Don't mirror by default
  note_template: "default"       # Frontmatter template
```

Extend `config.yaml` apple_notes section (system config):
```yaml
apple_notes:
  unified_inbox: "📥 Inbox"
  mirror_folder: "🔄 Augur Sync"   # Apple Notes folder for mirrored notes
  auto_ingest: true                 # Enable Apple Notes → local markdown polling
  ingest_interval_minutes: 5        # Poll frequency (Apple Notes has no fs events)
  legacy_inbox_notes: ...           # Existing
```

Note on split: `preferences.yaml` holds user-facing choices (editor, defaults). `config.yaml` holds system-level integration config (Apple Notes folder names, polling intervals). The filesystem watcher runs unconditionally when the daemon is active — no separate toggle needed.

## Consequences

### Positive

- Users get a seamless capture-anywhere-edit-anywhere workflow without Augur building an editor
- Mobile capture via Apple Notes is preserved and enhanced with auto-ingestion
- AI layer provides the "magic" editing features instead of a mediocre built-in editor
- MarkText (or any editor) remains user's choice — vendor-agnostic principle upheld
- Reverse sync enables mobile access to Augur content without cloud dependency
- Filesystem-driven approach aligns with ADR-109 philosophy

### Negative

- Filesystem watchers can be resource-hungry if not scoped carefully (mitigate: watch only `*/data/notes/` dirs, debounce 2s, Python `watchdog` scoped to specific paths)
- Apple Notes API via osascript is slow for large operations — 30s timeout per call (mitigate: circuit breaker on polling, per-note sync lock, async processing)
- One-way sync means edits in Apple Notes mirrors are lost (mitigate: explicit "DO NOT EDIT HERE" header in mirrored notes, last-write-wins semantics)
- MarkText must be installed separately (mitigate: graceful fallback to system default via ADR-114 resolution chain, first-run detection)

### Neutral

- Existing Apple Notes inbox pattern unchanged — just adding auto-ingestion on top
- RAG indexing may need `*/data/notes/` paths added to index config — verify during implementation whether these paths are already covered by existing glob patterns

## Alternatives Considered

### Alternative 1: Build an Embedded Markdown Editor

Integrate Milkdown, Tiptap, or similar into the dashboard. Rejected because:
- 2-3 months of engineering for a mediocre result
- Maintenance burden of keeping editor dependencies updated
- Users already have preferred editors — forcing a built-in one violates user sovereignty
- The AI layer is the differentiator, not the text editing surface

### Alternative 2: VSCode Fork

Fork VSCode/Cursor to get a built-in editor. Rejected because:
- Massive maintenance burden, developer-only UX
- Loses "personal AI OS" positioning entirely
- Overkill for note editing

### Alternative 3: Obsidian Integration

Use Obsidian as the editor via its plugin API. Considered but deferred because:
- Adds a heavy dependency (Obsidian is not open-source core)
- Obsidian's vault model conflicts with Augur's skill-based directory structure
- Could be a future plugin/integration, not a core architecture decision

### Alternative 4: Web-Based Editor (Monaco/CodeMirror)

Embed a code editor in the dashboard. Rejected because:
- Code editors are wrong UX for note-taking
- Still requires significant integration work
- Doesn't solve mobile capture/access

## References

- ADR-114: Centralized Editor Settings (editor routing foundation)
- ADR-080: Apple Hardening (Apple Notes MCP tools)
- ADR-109: Filesystem-Driven Dashboard (filesystem as source of truth)
- ADR-004: Markdown RAG (search across markdown content)
- Learned patterns: `config/system/learned-patterns.yaml` (inbox pattern)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR.

You are implementing **ADR-158: Seamless Note Editing Integration**.

Read the full ADR: `docs/decisions/ADR-158-seamless-note-editing-integration.md`

**Team name**: `adr-158-note-integration`

### Phase 1: Foundation + Config (PARALLEL)
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend | medium | Create standardized notes directory structure with `_index.cache.yaml` and frontmatter templates for 3 pilot skills: career (meetings/reviews), ideas-capture (Apple Notes inbox target), knowledge (research notes) | `plugins/*/skills/*/augur/data/notes/` |
| 1.2 | backend | medium | Implement Python filesystem watcher daemon task for notes directories — `watchdog`-based, debounced 2s, scoped to `*/data/notes/*.md`. On change: rebuild `_index.cache.yaml` from frontmatter, emit SSE event | Python daemon task |
| 1.3 | backend | low | Extend `preferences.yaml` with `notes` section and `file_editors.md: "MarkText"`. Extend `config.yaml` apple_notes with `mirror_folder` and `auto_ingest` settings | `config/system/preferences.yaml`, `config/system/config.yaml` |
| 1.4 | backend | low | Verify RAG index config covers `*/data/notes/*.md` paths — add glob if missing | RAG index config |

### Phase 2: Apple Notes Bridge (PIPELINE after 1.1, 1.3)
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | backend | medium | Implement auto-ingest Python daemon task: periodic poll (5 min) of Apple Notes inbox → AI-parse items → create local markdown with frontmatter → move to PROCESSED. Include circuit breaker (skip if previous poll in-flight) and 30s osascript timeout | Python daemon task |
| 2.2 | backend | medium | Implement reverse sync: on watcher event with `sync_to_apple: true` → convert markdown to plain text → `apple-create-note` or `apple-update-note` in mirror folder. Per-note sync lock, retry-once on failure, set `sync_status: failed` in cache on persistent error | Python daemon task |

### Phase 3: AI Commands (PARALLEL after 1.1 — no Apple bridge dependency)
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | backend | medium | Implement `/note-create` slash command — create note from conversation context, place in skill dir, open in editor via ADR-114 | MCP tool + command YAML |
| 3.2 | backend | medium | Implement `/note-promote` — take an Apple Notes inbox item and expand into a full structured markdown note with AI-generated frontmatter and structure | MCP tool + command YAML |
| 3.3 | backend | low | Implement `/note-sync` — manual trigger for Augur → Apple Notes push for a specific note | MCP tool |
| 3.4 | backend | medium | Implement `/note-search` — RAG-powered note search surfaced as dedicated command | MCP tool wrapping existing RAG |

### Phase 4: Dashboard Integration (PARALLEL with Phase 2, after 1.1, 1.2)
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | frontend | medium | Add "Edit in MarkText" button to note views in dashboard — calls `system-open` with editor resolution | Dashboard skill pages |
| 4.2 | frontend | low | Add note creation modal with skill selector and template picker | Dashboard components |
| 4.3 | frontend | low | Wire filesystem watcher SSE events to dashboard auto-refresh | Dashboard event handling |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | validator | medium | End-to-end test: create note in Apple Notes → verify auto-ingest → edit in MarkText → verify sync back to Apple Notes |
| V.3 | validator | low | Resilience test: verify graceful behavior when Apple Notes is closed, MarkText is not installed, osascript times out, note has invalid frontmatter |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria
- [ ] Notes directory structure created for pilot skills with `_index.cache.yaml`
- [ ] Filesystem watcher (Python `watchdog`) detects markdown changes and rebuilds cache
- [ ] Apple Notes inbox items auto-ingested to local markdown with circuit breaker
- [ ] Reverse sync pushes notes to Apple Notes mirror folder with sync lock
- [ ] `/note-create` and `/note-promote` slash commands functional
- [ ] Dashboard "Edit" button opens MarkText via ADR-114 routing
- [ ] RAG index confirmed to cover `*/data/notes/` paths
- [ ] End-to-end flow verified: Apple Notes → Augur → MarkText → Apple Notes mirror
- [ ] Graceful degradation verified: missing MarkText, Apple Notes closed, osascript timeout
- [ ] All tests pass
- [ ] ADR status updated to Accepted
