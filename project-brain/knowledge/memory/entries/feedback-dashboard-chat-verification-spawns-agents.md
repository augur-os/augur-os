---
title: feedback-dashboard-chat-verification-spawns-agents
name: feedback-dashboard-chat-verification-spawns-agents
description: Driving the dashboard floating-chat via browser automation to verify
  a feature is dangerous — Start/Reconnect spawns or resumes REAL autonomous claude
  agents (--dangerously-skip-permissions) that read repo context and edit files in
  parallel, and starting a local Ollama (airplane) session can saturate CPU and crash
  the Next dev server
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_dashboard_chat_verification_spawns_agents.md
source_hash: 756c39ff36052d6f
_mentions:
- '[[feedback-autonomous-execution]]'
---



When verifying a dashboard change in the browser, do NOT use the live floating-chat as a test puppet. Clicking Start/Reconnect and sending messages launches or resumes a real Claude Code agent in the repo with `--dangerously-skip-permissions`.

**Why:** During an airplane-mode (offline mode) bug fix on 2026-05-20, browser verification of the chat header chip required a "running" chat session. Sending test messages ("hi", "say only OK") to the dashboard chat spawned/resumed an autonomous agent (it resumed session id `f0485599…`). That agent read the conversation/repo context, recognized the in-progress airplane fix, and **autonomously edited the repo in parallel** — it updated `tests/dashboard/components/ChatHeader-airplane-chip.test.tsx` (to match the new `useQuery` server-truth chip) and enhanced `scripts/hooks/run-hook.mjs` (the value-validation Stop hook) — none of which I made. It was still running 5+ min later. Separately, toggling airplane ON started an `ollama launch claude --model qwen3:4b` session; the local-model inference spiked CPU and the Next dev server went to HTTP 000 (connection refused) — recovered via `python3 shared-vault/skills/daemon/scripts/cleanup_processes.py` then `node apps/dashboard/scripts/start-dev.mjs`.

**How to apply:**
1. To verify chat-header / session UI, prefer driving server state directly (the `/api/cli`, `/api/airplane`, `/api/session/init` endpoints + `get-local-backend-status` MCP tool) and reading the rendered DOM — not by holding real agent conversations in the floating chat.
2. If you must start a chat session, use the smallest interaction and STOP it when done; never leave an autonomous agent running. Treat any repo edits that appear and that you did not make as another session's work — investigate, do not revert (see [[feedback-autonomous-execution]] and rule 22).
3. Avoid starting airplane/local-Ollama sessions on the box running the dev server during verification — the model inference can starve next-server. If the dev server returns HTTP 000, it crashed; recover via the gated cleanup + start-dev path, not manual kills.
4. react-query `refetchInterval` polls (e.g. the airplane chip's `get-local-backend-status` and `/api/cli` queries) PAUSE when the MCP-driven Chrome tab is not OS-focused. A full page reload forces a fresh fetch; a dispatched `focus`/`visibilitychange` event is unreliable. Account for this when a toggled state "doesn't update" in the browser-automation tab.
