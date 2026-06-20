# IDE Interaction Modes Simplification

**Date:** 2026-04-20
**Status:** Approved

## Problem

The current IDE interaction system has accumulated too many execution concepts: `fire`, `oneshot`, `ide`, `chat`, `auto`, `modal`. Each maps to a different execution path, some web-only (fire = direct MCP call), some poorly defined (auto). The context envelope prepends Page/Hub/Skill/Tools/Project sections before every prompt — noise the agent doesn't need. The browse page shows action buttons but has no dedicated prompts or commands surface. There is no pre-warmed session — every interaction cold-starts a CLI.

## Principles

- **Web is a thin launcher.** Everything possible in the web is also possible in the CLI. No web-only execution paths except data-entry modals.
- **Prompts are the primary concept.** Text sent to an LLM via the CLI. Nothing else.
- **Commands are CLI invocations.** Slash commands that execute in the CLI, not MCP calls from the web.
- **Results come to the user.** Browse stays open. Results render inline. No forced context switches.

---

## Section 1: Schema (file-based, not frontmatter)

**Prompts and commands are NOT added to SKILL.md frontmatter.** They live as individual files in standard Agent Skills directories. Each file is one prompt or command. SKILL.md is not modified.

```
skills/<skill>/
├── SKILL.md                       (untouched)
├── commands/                      (Agent Skills standard — already exists)
│   └── <command-id>.md
└── prompts/                       (proposed standard — see proposals/)
    └── <prompt-id>.md
```

### File format (identical for prompts and commands)

```markdown
---
id: agentic-search
label: Agentic Search
description: Search across your knowledge base using AI
icon: Search
---

Search for: {{query}}
```

- **Frontmatter** = metadata for the dashboard browse UI (id, label, description, icon, tags)
- **Body** = the literal prompt text or command spec sent to the LLM/CLI
- `{{var}}` placeholders in the body get substituted at invocation. Multiple distinct vars supported. The same value is substituted for every occurrence of `{{name}}`.

### Distinction

| `commands/<id>.md` | `prompts/<id>.md` |
|---|---|
| Slash-command spec — body describes what `/<id>` does | Raw text sent to the LLM as a user message |
| CLI executes via its slash-command system | Sent verbatim via print mode |
| Already exists — 90+ files in repo | New directory, new convention |

### Why directory-based, not frontmatter

- **Portable**: Claude Code, Codex, Gemini CLI all already discover `commands/` from skill directories. Same pattern for `prompts/`.
- **Single source of truth**: The same file the CLI reads is the same file the dashboard reads. No duplication.
- **Per-item diff/review**: Adding a prompt = one new file, not a frontmatter mutation.
- **No SKILL.md churn**: 70+ skills' frontmatter remains untouched.
- **Upstream contribution**: A formal proposal for `prompts/` is documented at `docs/superpowers/proposals/agent-skills-prompts-directory.md` for submission to the Agent Skills standard.

### Retired

- `actions:` with `dispatch: fire/oneshot/ide/chat/auto` — all migrated into `prompts/` or `commands/` files
- `dispatch: modal` — rare exception, stays in `actions:` explicitly, not a growth path

---

## Section 2: Browse Page UX

Skill detail page gains four tabs: **Overview**, **Prompts**, **Commands**, **Integration**.

### Prompts tab

One card per `prompts:` entry.

- `{{var}}` in prompt → inline text input on card, user types and hits Run
- No `{{var}}` → single Run button, fires immediately on click
- While running: spinner on card, input disabled
- Result renders below card as a result card:
  - Final answer rendered as markdown
  - "Continue in session →" link — opens active CLI panel with `--resume <session-id>`
  - Copy button
- Multiple prompt cards run independently, each has own result state
- No navigation away from browse

### Commands tab

Same card pattern as prompts. No input field. Shows command string. Same result card + "Continue in session →" pattern.

### Integration tab

CLI reference for the skill:

- Shows active default CLI name
- Renders live output of `augur <skill> --help`
- Lists all commands with descriptions — mirrors `commands:` entries in SKILL.md

### What's removed from browse

- Context envelope (Page/Hub/Skill/Tools/Project sections) — no longer prepended to prompts
- Action buttons with `dispatch: fire/ide/chat` — replaced by Prompts + Commands tabs
- Old "action-dialog" chat view for IDE dispatch from browse

---

## Section 3: Session Manager

One pre-warmed default CLI session per dashboard session. A new `SessionManager` owns the PTY lifecycle independently of the chat panel UI.

### Lifecycle

```
Dashboard loads
  └─ SessionManager reads last session ID from state dir
  └─ Spawns default CLI: claude --resume <last-id>  (fresh start if none)
  └─ PTY runs silently in background — panel hidden

User opens chat panel
  └─ Panel attaches to already-running stream → instant, no cold start

User closes chat panel
  └─ Panel detaches from stream — PTY keeps running in background
  └─ Reconnect is instant (stream reattach, not respawn)

Dashboard unloads / tab closes
  └─ PTY terminates gracefully
  └─ Session ID saved to state dir → used on next load
```

### Resume chain

| Load | Command |
|------|---------|
| First ever | `claude` (fresh) → saves session-id |
| Subsequent | `claude --resume <last-id>` → history restored |

Applies equally across CLIs:

| CLI | Resume command |
|-----|---------------|
| claude | `claude --resume <session-id>` |
| codex | `codex resume --last` or `codex resume <session-id>` |
| gemini | `gemini --resume <uuid>` *(session ID from headless JSON output — degrades to `--resume` latest until issue #14435 resolved)* |

### Collision handling

When "Continue in session" is triggered while a conversation is already active:

```
⚠️  Session already active
[View current session]  [Replace with new]
```

- **View current session** — opens panel to existing conversation
- **Replace with new** — sends new prompt, previous context preserved in history

### Codebase changes

- `SessionManager` replaces ad-hoc `startCliProcess` calls for the main CLI
- `chatStore` open/close no longer spawns/kills PTY — attaches/detaches from stream
- Session ID stored alongside existing `chat_session.json` in state dir

---

## Section 4: Execution Pipeline

### Print-mode run flow

```
User clicks Run on browse prompt card
  ├─ Client collects {{var}} input (if any), resolves prompt string
  └─ POST /api/cli/exec  { prompt: "..." }   ← no cliId: server always uses configured default
       ├─ Server resolves default CLI from cli_agents.yaml
       ├─ Spawns short-lived PTY with print_cmd template
       ├─ Streams JSONL events via SSE → GET /api/cli/exec/stream?id=xxx
       └─ Client extracts final answer + session_id → renders result card
```

### Per-CLI command resolution

| CLI | Print mode command |
|-----|-------------------|
| `claude` | `claude -p "{prompt}" --output-format stream-json` |
| `codex` | `codex exec "{prompt}" --json` |
| `gemini` | `gemini --prompt "{prompt}" --output-format stream-json` |

Configured via `print_cmd` template in `cli_agents.yaml`. No hardcoding in route code.

### Result card data model

```ts
interface PromptResult {
  promptId: string
  input: string        // resolved prompt sent to CLI
  answer: string       // extracted final answer (markdown)
  sessionId: string    // for --resume on "Continue in session"
  cliId: string
  durationMs: number
  timestamp: Date
}
```

Stored in component state only — not persisted. Browse is a launcher, not a history viewer.

### "Continue in session" wiring

```
User clicks "Continue in session"
  ├─ SessionManager: is default CLI session running?
  │    ├─ YES → send "Previous result:\n{result.answer}\n\nContinue from here."
  │    │        as next message into active session → open panel
  │    └─ NO  → open panel, CLI starts with --resume <result.sessionId>
  │              (full history including the print-mode run is restored)
  └─ User sees conversation with prior context intact
```

### Retired

- `/api/actions/oneshot` route → replaced by `/api/cli/exec`
- `buildPromptFromEnvelope` for browse triggers → eliminated
- `resolveContext` calls in browse dispatch paths → eliminated
- 6-second `setTimeout` prompt injection hack → replaced by print mode

---

## Section 5: Migration

### Retired concepts

| Old | Replaced by |
|-----|-------------|
| `actions:` with `dispatch: oneshot/ide/chat/auto` | `prompts:` |
| `actions:` with `dispatch: fire` | `commands:` |
| Context envelope for browse | Raw prompt string |
| `/api/actions/oneshot` | `/api/cli/exec` |
| Agent bubbles for browse | Inline result cards |
| `resolveContext` in browse paths | Eliminated |

### What stays

- `dispatch: modal` — rare exception in `actions:`, not migrated
- `useActionRunner` for hub feature pages (geo, career, websites) — out of scope
- `chatStore` / chat panel — still owns interactive session UI
- `agentBubbleStore` — kept for non-browse contexts, cleaned up in follow-on

### Migration script

One-time script over all `skills/*/SKILL.md`:

```
For each action in actions:
  dispatch: fire              → write file: skills/<skill>/commands/<id>.md (if not already present)
  dispatch: oneshot|ide       → write file: skills/<skill>/prompts/<id>.md
  dispatch: chat|auto         → write file: skills/<skill>/prompts/<id>.md
  dispatch: modal             → stays in actions: (logged as exception)
After: remove migrated entries from SKILL.md actions: array
```

Each generated file has frontmatter (id, label, description, icon) and a body containing the prompt text (for prompts) or a one-line command spec (for commands). Existing `commands/*.md` files are not overwritten — the script skips writing if a file already exists for the given id.

~70 skills. Dry-run diff first, then apply.

### Implementation order

1. `/api/cli/exec` route + `print_cmd` field in `cli_agents.yaml`
2. `SessionManager` — pre-warm, resume chain, collision toast
3. Browse page tabs — Prompts, Commands, Integration
4. Inline result card component + "Continue in session" wiring
5. Migration script — schema conversion across all skills
6. Retire old routes + `buildPromptFromEnvelope` browse paths
