---
status: Implemented
date: 2026-04-20
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-590: IDE Interaction Modes

## Context

The dashboard's IDE interaction system has accumulated too many execution concepts: `fire`, `oneshot`, `ide`, `chat`, `auto`, `modal`. Each maps to a different execution path, some web-only (`fire` = direct MCP call), some poorly defined (`auto`). The context envelope prepends Page/Hub/Skill/Tools/Project sections before every prompt — noise the agent does not need. The browse page shows action buttons but has no dedicated prompts or commands surface. Every interaction cold-starts a CLI; there is no pre-warmed session.

The right model is much simpler: web is a thin launcher, prompts are the primary concept (text sent to an LLM via the CLI), commands are CLI invocations, and results come back to the user inline without forcing a context switch.

## Decision

Replace the five-mode dispatch system with a file-based prompts/commands convention, a clean print-mode exec route, a pre-warmed session, and a tabbed browse page:

**Schema (file-based, not frontmatter):**
- Prompts and commands live as individual `.md` files in `skills/<skill>/prompts/<id>.md` and `skills/<skill>/commands/<id>.md`. SKILL.md is not modified.
- Each file: frontmatter (`id`, `label`, `description`, `icon`) + body (raw prompt text or command spec). `{{var}}` placeholders are substituted at invocation.
- `commands/` is the existing Agent Skills standard. `prompts/` is a proposed standard documented for upstream contribution.

**Execution pipeline:**
- New `POST /api/cli/exec` route resolves the configured default CLI from `cli_agents.yaml`, spawns a short-lived PTY using each CLI's `print_cmd` template (`claude -p "{prompt}" --output-format stream-json`, `codex exec "{prompt}" --json`, `gemini --prompt "{prompt}" --output-format stream-json`), and streams JSONL events via SSE on `/api/cli/exec/stream?id=xxx`.
- The context envelope (`buildPromptFromEnvelope`, `resolveContext` for browse) is eliminated. Browse sends raw prompt strings.

**Session manager:**
- A new `SessionManager` singleton owns the default CLI PTY lifecycle independently of the chat panel. On dashboard load it spawns `claude --resume <last-id>` (fresh start if none) silently in the background. Opening the chat panel attaches to the running stream; closing detaches without killing. PTY terminates on dashboard unload; session ID persists in the state dir for the next load.
- Resume chain applies across CLIs (`claude --resume`, `codex resume --last`, `gemini --resume`).
- Collision toast when "Continue in session" fires while a conversation is active: View current session / Replace with new.

**Browse UX:**
- Skill detail page gains four tabs: Overview, Prompts, Commands, Integration. Prompt cards render `{{var}}` inputs, run via `/api/cli/exec`, render result inline (markdown answer + Continue in session + Copy). Command cards run a slash command. Integration tab renders live `augur <skill> --help`.

**Migration:**
- One-time `scripts/migrate_actions_to_prompts.py` converts existing `actions:` entries (`fire` → `commands/<id>.md`, `oneshot|ide|chat|auto` → `prompts/<id>.md`). `dispatch: modal` stays in `actions:` as a logged exception. Existing `commands/*.md` files are preserved.

## Consequences

### Positive
- One conceptual model: prompts are LLM text, commands are CLI invocations
- No web-only execution paths (except data-entry modals)
- Pre-warmed session removes cold-start latency on chat panel open
- Prompts and commands are portable across Claude Code, Codex, Gemini CLI via standard skill directories
- Per-item diff/review (one new file per prompt) instead of frontmatter mutations
- 70+ skills' SKILL.md frontmatter remains untouched

### Negative
- One-time migration touches ~70 skills (dry-run diff first, then apply)
- Gemini session ID resume currently degrades to latest until upstream issue #14435 resolves
- `dispatch: modal` stays as a small explicit exception rather than a clean break

### Neutral
- `useActionRunner` for hub feature pages (geo, career, websites) is out of scope
- `chatStore` / chat panel still owns interactive session UI
- `agentBubbleStore` retained for non-browse contexts; cleanup deferred

## Alternatives Considered

### Alternative 1: Keep dispatch modes, just simplify them
Rejected: the conceptual sprawl is the problem, not the implementations of individual modes. Five modes collapse cleanly into prompts vs. commands.

### Alternative 2: Encode prompts/commands in SKILL.md frontmatter
Rejected: 70 skills' frontmatter would churn, per-item diffs would be harder, and CLIs already discover `commands/` from skill directories — `prompts/` follows the same proven shape.

### Alternative 3: Spawn CLI per chat panel open
Rejected: cold-start on every open is the user-visible pain. Pre-warming with detach/attach gives instant reconnect.

## References
- Plan: docs/superpowers/plans/2026-04-20-ide-interaction-modes.md
- Spec: docs/superpowers/specs/2026-04-20-ide-interaction-modes-design.md
