---
title: augur-cross-client-never-claude-only
name: augur-cross-client-never-claude-only
description: Augur is cross-client (Claude/Codex/Gemini/Copilot/Cowork) — never assume
  only Claude is used; concurrent sessions and shared logic are client-agnostic
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: augur-cross-client-never-claude-only.md
source_hash: 2f80790f79e96189
_mentions:
- '[[sdlc-autonomy-aug-dev-build]]'
---



Augur is a cross-client system: it runs across Claude Code, Codex, Gemini, Copilot, Cowork, and future clients. The "active client" is whichever launched the session — it is NOT always Claude. NEVER assume Claude is the only client, the only running session, or the canonical one.

**Why:** The user corrected me after I described a concurrent session that had pushed to origin/main + co-edited memory as "another Claude session" — it could be any client. Augur's worktree/dashboard/memory/registry state is shared across clients, and client-specific runtime (Claude's `EnterWorktree`/`WorktreeCreate`/`WorktreeRemove` hooks + `.claude/`, Codex `.codex/`, Gemini `.gemini/`) is just one client's adapter onto a shared model.

**How to apply:**
- A concurrent/parallel session, an existing worktree, a pushed commit, or an edit to shared state (memory, registry, purge queue) may belong to ANY client — say "another session/client", never "another Claude session".
- Shared behavior (worktree create/remove + cleanup, MCP config, registry, hook-driven logic) lives in client-neutral engines (shared Python/bash); each client's hook/launcher is a thin entry into that shared logic, never a Claude-only path. Fixing one client's adapter must not regress another's.
- Ownership/cleanup checks must be cross-client (`active_ai_processes_for_path` covers every client); merges + memory writes must tolerate concurrent writers from other clients (append/merge, don't clobber).
- When you catch yourself writing "Claude" where you mean "the active client", fix it.

Encoded as **rule 38** in `docs/agent-topics/agent-rules.md` (projects to `CLAUDE.md`). See [[sdlc-autonomy-aug-dev-build]] (the cross-client worktree create/remove cleanup) and rules 24, 26, 30, 35.
