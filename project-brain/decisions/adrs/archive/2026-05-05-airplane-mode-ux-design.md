# Airplane Mode UX & Local-Backend Routing

**Date:** 2026-05-05
**Status:** Draft
**Supersedes (in part):** `docs/superpowers/specs/2026-03-28-local-mode-ollama-design.md`
**Primary platform target:** Windows + macOS (Ollama runs primarily on Windows)
**Scope:** End-to-end airplane mode — toggle placement, in-chat visibility of local vs remote backend, and actual agent-launch routing through Ollama.

## Overview

Today, Augur has the foundational MCP tools (`toggle-airplane-mode`, `get-local-backend-status`), a `/airplane` slash command, and a SecurityTab toggle, but the airplane mode is largely cosmetic at the routing level: flipping it ON only strips auto-approve flags from the spawned CLI; it does not change which backend the agent talks to. The toggle also lives only in **Settings → Security**, far from where users work, and the chat UI does not signal whether the running agent is using a cloud or local model.

This design closes those gaps with three coordinated changes:

1. **Surface the toggle** at the dashboard top-bar (canonical) and mirror its state in the chat header (chip), so it is reachable from anywhere and unambiguous about the running agent.
2. **Show transitions in chat history** with a single inline system message when airplane state flips mid-session, so chat history reads correctly.
3. **Wire the toggle to actually change agent routing** by spawning supported agents through `ollama launch <agent>`, using Ollama's own per-agent integration knowledge instead of a hand-rolled per-agent strategy table in Augur.

The single source of truth for airplane state and the configured local model is `preferences.yaml`. The browser-side localStorage `airplaneModeStore` is replaced by a thin selector around a `useMcpQuery` call against `get-local-backend-status`, eliminating the current client/server desync. All consumers share a single React-Query cache key (e.g. `"airplane-status"`) so one invalidation re-renders pill, chip, and SecurityTab in sync. Following the project's `useMcpQuery(cacheKey, toolName, ...)` convention (see `SecurityTab.tsx:204`), the cache key and the MCP tool name are passed as separate arguments.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Toggle placement: global top-bar pill (canonical) + mirror chip in chat header. Settings → Security keeps deep config but is no longer the only flip point. | The toggle is reachable from anywhere; the chat chip makes the running agent's backend unambiguous. |
| 2 | In-chat visibility: header chip + inline system marker on transitions. No per-message tags. | Clean history; transitions anchored to a visible breadcrumb. Per-message tags add visual noise without proportional value in v1. |
| 3 | Launch mechanism: defer to `ollama launch <agent>` for any agent in Ollama's integration list. | 11 agents wrapped natively (claude, cline, codex, copilot, droid, hermes, kimi, opencode, openclaw, pi, vscode). Zero per-agent maintenance for Augur. Ollama owns per-agent quirks (codex `--oss`, opencode `opencode.json`, claude env vars). |
| 4 | Auto-detect connectivity: out of v1. Manual toggle only. | "Forced" vs "auto-flipped" semantics create UI ambiguity in the chip; manual toggle is unambiguous. The watchdog code in `connectivity.py` stays unused for now. |
| 5 | Failure UX: soft toggle + pre-flight check at agent spawn. Toggle always flips; spawn returns 409 with `setup_hint` when Ollama isn't ready. | Flipping behavior is predictable; failure surfaces at the right boundary (agent spawn) where we already have an error path. |
| 6 | Single shared local LLM in v1. Per-agent overrides are out of scope. | Matches the user's stated simplification. The `local_backends.ollama.model` field is the one model all supported agents use. |

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │          preferences.yaml (canonical)        │
                    │   airplane_mode: { enabled, forced }         │
                    │   local_backends.ollama: { binary, model }   │
                    └────────────┬───────────────┬────────────────┘
                                 │ MCP           │ MCP
                                 │ get-local-    │ toggle-airplane-mode
                                 │ backend-status│
                ┌────────────────┴───────┐       │
                │                        │       │
        ┌───────▼────────┐      ┌────────▼───────▼──────┐
        │  Top-bar pill  │      │  Chat header chip      │
        │  (global)      │      │  (mirror, in-chat)     │
        └───────┬────────┘      └────────┬───────────────┘
                │ click                  │ click
                └───────────┬────────────┘
                            ▼
                ┌──────────────────────┐
                │ /api/airplane (POST) │ ──► toggle-airplane-mode MCP
                └──────────────────────┘     (single endpoint, single source of truth)

                  ┌─────────────────────────────────────────┐
                  │  CLI start path (apps/dashboard/api/cli)│
                  │  ──────────────────────────────────────  │
                  │  1. Read prefs (airplane + local_backend)│
                  │  2. If airplane ON:                       │
                  │       a. pre-flight via get-airplane-     │
                  │          launch-overrides MCP             │
                  │       b. if not ready → 409 + setup_hint  │
                  │       c. if ready → prepend               │
                  │          ["ollama","launch",cliId,        │
                  │           "--model",model,"--"]           │
                  │  3. spawn PTY                             │
                  └─────────────────────────────────────────┘
                                  │
                                  ▼
                        ┌────────────────────┐
                        │  Same cli binary   │  → talks to localhost:11434
                        │  wrapped by ollama │     (Ollama serves on macOS,
                        │  launch            │      Windows, Linux)
                        └────────────────────┘
```

The toggle, the chip, and the CLI launcher all read from one server-owned source via existing MCP tools. The dashboard never spawns subprocesses or touches `fs` directly — it goes through `/api/mcp/tool` (project rule 11). The browser store becomes a query cache, not a write target.

## Components

### New files

1. **`src/mcp/augur_mcp/infrastructure/local_backends.py`** *(extend)*
   - `list_ollama_integrations_impl()` — runs `ollama launch --help` once, parses the integration list (claude, cline, codex, copilot, droid, hermes, kimi, opencode, openclaw, pi, vscode), caches 60s.
   - `get_airplane_launch_overrides_impl(agent_id)` returns a discriminated union:
     ```ts
     | { ready: true; integration_id: string; model: string; launch_argv: string[] }
     | { ready: false; reason: "binary_missing"|"ollama_not_running"|"model_missing"; setup_hint: string }
     | { ready: false; reason: "unsupported"; setup_hint: string }
     ```
   - Platform-aware binary detection: `shutil.which("ollama")` first, then probe Windows candidates (`%LOCALAPPDATA%\Programs\Ollama\ollama.exe`, `%PROGRAMFILES%\Ollama\ollama.exe`), then macOS/Linux candidates (`/opt/homebrew/bin/ollama`, `/usr/local/bin/ollama`, `~/.local/bin/ollama`).
   - Platform-aware setup hints (see Error Handling section).
   - `get-airplane-launch-overrides` is also registered in `infrastructure/__init__.py` and added to `CURATED_VISIBLE_TOOLS` in `client_surface.py`, following the existing pattern for `toggle-airplane-mode` and `get-local-backend-status`.

2. **`apps/dashboard/components/shared/AirplanePill.tsx`**
   - Global top-bar pill with four visual states: `off` (gray cloud), `on-ready` (amber filled, model name), `on-not-ready` (red outline, "Setup needed"), `on-unsupported` (warning icon, used in chat-header chip variant when current cliId is not in the Ollama integration list).
   - Reads `useMcpQuery("airplane-status", "get-local-backend-status", ...)`. POSTs to `/api/airplane` on click. Cache key `"airplane-status"` is shared across all consumers (pill, chip, SecurityTab, FloatingChat).

3. **`apps/dashboard/app/api/airplane/route.ts`**
   - Thin POST endpoint accepting `{ action: "on" | "off" | "toggle" }`. Wraps `mcpCall("toggle-airplane-mode", ...)`. Invalidates the `["get-local-backend-status"]` query key on success so all consumers re-fetch.

### Modified files

4. **`apps/dashboard/app/api/cli/actions.ts`** — `handleStartAction`:
   - Read airplane state from `preferences.yaml` via MCP (canonical) — request body's `airplaneMode` is treated as a hint, not authoritative, so refreshes don't desync.
   - When airplane ON, call `get-airplane-launch-overrides`. If `ready: false`, return `409 { error, setup_hint }`. If `ready: true`, replace argv with `launch_argv` (e.g. `["ollama","launch","claude","--model","qwen3.5:9b","--", ...originalConfig.cmd.slice(1)]`).
   - cwd and env are kept identical to the cloud spawn path — only the argv changes.

5. **`apps/dashboard/features/components/chat/ChatHeader.tsx`** — add mirror chip alongside the existing CLI label and online dot. Reads the same shared cache key as the global pill.

6. **`apps/dashboard/features/hooks/useCliChat.ts`** — emit a transition system message when `airplane_mode.enabled` flips during a running session, just before the existing stop/start cycle (`FloatingChat.tsx:148-158`). Surface 409 `setup_hint` from `/api/cli` start failures as an inline system message; if the hint contains a shell command, render it monospace with a copy button.

7. **`apps/dashboard/app/settings/tabs/SecurityTab.tsx`** — expand the existing lone airplane toggle into a **Local backend** subsection: detected ollama path (read-only), model dropdown populated from the Ollama installed-models list, "Test connection" button, **agent compatibility matrix** showing which configured CLIs are airplane-capable (and why each unsupported one isn't, e.g. `gemini: not in Ollama integration list`).

### Refactored

8. **`apps/dashboard/lib/stores/airplaneModeStore.ts`** — remove localStorage logic. Replace exported `useAirplaneModeStore` with a thin hook that reads from `useMcpQuery("airplane-status", "get-local-backend-status", ...)`. All call sites (FloatingChat, SecurityTab, AirplanePill, ChatHeader) keep working but read from canonical server state. Eliminates the long-standing client/server desync.

### Not built in v1

- `local_backends.yaml` per-agent strategy table (Path B's env/flags/config_file dispatcher) — replaced by `ollama launch`.
- Connectivity watchdog auto-detect.
- Per-agent model override.
- Non-Ollama backends (vLLM, LM Studio).
- Model-pull progress UI.
- Auto-fallback to cloud when local is unhealthy (explicitly rejected).

## Data flow

### Flow 1 — User clicks the top-bar pill (or chat-header chip) to turn airplane ON

```
1. User clicks AirplanePill (or ChatHeader chip)
2. POST /api/airplane { action: "on" }
3. Handler → mcpCall("toggle-airplane-mode", { action: "on" })
4. tool writes preferences.yaml: airplane_mode.enabled = true, forced = true
5. Handler invalidates the React-Query cache key ["get-local-backend-status"]
6. AirplanePill, ChatHeader chip, SecurityTab all re-fetch and re-render
7. If a CLI is currently running:
   - useCliChat pushes transition system message into chat:
     "✈ Airplane mode ON — switching claude → qwen3.5 (local)"
   - existing useEffect (FloatingChat.tsx:148-158) detects the airplane
     change and triggers stopCli → startCli, which respawns through
     `ollama launch`.
```

The pill click does not directly restart the CLI. The CLI restart is a derived effect, keeping the toggle action atomic.

### Flow 2 — CLI start while airplane is ON

```
useCliChat.startCli(cliId)
  → POST /api/cli { action: "start", cliId, ... }
  → handleStartAction reads canonical airplane state from preferences
  → mcpCall("get-airplane-launch-overrides", { agent_id: cliId })
       ├── ready=true: argv = ["ollama","launch",cliId,"--model",model,"--", ...rest]
       │              spawnPty(argv, cwd, env)
       │              return 200 { pid }
       │
       ├── ready=false (binary_missing | ollama_not_running | model_missing | unsupported):
       │              return 409 { error, setup_hint }
```

Client-side, `useCliChat.startCli` already has an error path (line 343-355). It is extended to render `setup_hint` as a monospaced inline system message when applicable.

### Flow 3 — User changes the local model

```
SecurityTab → useMcpQuery("airplane-status", "get-local-backend-status", ...)
              (the same query already returns the installed models list,
               so no separate "list-ollama-models" tool is needed in v1)
User picks "llama3.2:3b" from the dropdown → mcpCall("update-preference", {
  key: "local_backends.ollama.model",
  value: "llama3.2:3b"
})
preferences.yaml updated → cache key invalidated → all chips re-fetch.
If airplane is ON and a CLI is running, the same restart effect (Flow 1 step 7)
fires, respawning the agent with the new model and a new transition system
message.
```

### State invariants

- **Single source of truth:** `preferences.yaml`. Everything else is derived.
- **No client-side write:** the browser never writes localStorage for airplane state. It only POSTs to `/api/airplane` or calls `update-preference` MCP.
- **Cache key contract:** `["get-local-backend-status"]` is shared by AirplanePill, ChatHeader chip, SecurityTab, and FloatingChat. One invalidation re-renders them all in sync.
- **CLI restart is a derived effect**, not a primary action. Toggling the pill is allowed to do nothing visible in chat if no CLI is running.

## Error handling

### Pre-flight (`get-airplane-launch-overrides`)

| Condition | `reason` | macOS hint | Windows hint |
|---|---|---|---|
| Binary not on PATH and not in candidate locations | `binary_missing` | `Install: brew install ollama` | `Install from https://ollama.com/download/windows or run: winget install Ollama.Ollama` |
| Binary present but `ollama list` fails | `ollama_not_running` | `Run: ollama serve` | `Open the Ollama app from Start menu (or run: ollama serve in PowerShell)` |
| Server up but configured model not in `ollama list` | `model_missing` | `Run: ollama pull <model>` | `Run in PowerShell: ollama pull <model>` |
| Agent not in parsed `ollama launch --help` integration list | `unsupported` | `Switch to claude, codex, opencode, or another supported agent for airplane mode` | (same) |
| Old Ollama version (no `launch` subcommand) | `binary_missing` | `Update: brew upgrade ollama` | `Reinstall from https://ollama.com/download/windows` |

All five share a single 409 response shape. The hint string is rendered as a system message in chat; if it contains a shell command, it is monospace-formatted with a copy button.

### Spawn

| Condition | Recovery |
|---|---|
| `ollama launch <agent>` exits immediately (Ollama bug, integration broken) | Existing PTY exit handler (`useCliChat.handleCliExit`) catches it; chat shows exit code and stderr. **No auto-fallback to cloud** — that would silently violate user intent. |
| Spawn succeeds but PTY produces no output for >30s | Existing `useCliHealthPoller` covers this. Same path; chat shows "agent unresponsive" with stop button. |
| User flips airplane OFF mid-stream | `prevAirplaneModeRef` effect runs `stopCli` → `startCli`. Transition system message: `✈ Airplane mode OFF — switching qwen3.5 → claude (cloud)`. In-flight Ollama response is killed. |

### Toggle endpoint

| Condition | Recovery |
|---|---|
| `POST /api/airplane` fails (e.g. preferences.yaml unwritable) | Pill shows toast: "Couldn't update airplane state — check filesystem permissions". State stays whatever it was. No optimistic UI; pill reflects server. |
| Rapid clicks (race) | Idempotent at prefs layer; React Query coalesces in-flight mutations. |
| Concurrent change from `/airplane` slash command and dashboard pill | Both go through `toggle-airplane-mode` MCP. Last-write-wins on `preferences.yaml`. Cache invalidation triggers re-fetch on both clients. |

### Pre-existing chat session when airplane state changes

- **Airplane ON while session is running on cloud:** transition system message **before** stopCli, so chat history shows: prior cloud message → transition marker → restart → first local response. The agent loses conversational memory across the restart — known v1 limitation; transition message implicitly cues the user that context is fresh.
- **Airplane OFF while session is running on local:** symmetric.
- **Airplane state changes while no CLI is running:** no restart, no system message in chat. Pill/chip update silently. Next CLI start uses the new mode.

### Out of scope explicitly

- Network interruption to local Ollama mid-request — treated as PTY exit.
- Auto-fallback to cloud — explicitly rejected; would leak data the user wanted kept local.
- Multi-model routing — single shared LLM in v1.
- Auto-migration of detached sessions across airplane toggles — detached sessions stay on whichever backend they started on until reconnected and explicitly restarted.

## Testing strategy

### Layer 1 — MCP infrastructure (Python contract tests)

`tests/packages/augur-mcp/tools/test_local_backends.py` *(extend)*:

- `list_ollama_integrations_impl`: parses `ollama launch --help` output (mock the actual help text); returns empty list when binary is missing or `launch` subcommand is unknown; cache TTL respected (subprocess called once per 60s window).
- `get_airplane_launch_overrides_impl`: covers all five `reason` cases. `ready: true` returns correct `launch_argv` shape. Platform-parametrized via `monkeypatch.setattr(sys, "platform", ...)` to verify both candidate-path probes and hint strings on macOS and Windows.

### Layer 2 — `/api/cli` start path (TypeScript)

`tests/dashboard/api/cli-route-airplane.test.ts` *(new)*:

- When override returns `ready: true`, spawned argv is `["ollama","launch",cliId,"--model",m,"--", ...rest]` (verified via mock pty spawn capture).
- When override returns `ready: false`, route returns 409 with `setup_hint`.
- Body's `airplaneMode` hint is overridden by canonical preferences value.
- When airplane is off, no override call is made; original cmd spawned unchanged.

Mocks `mcpCall` and `node-pty.spawn`. No real Ollama dependency.

### Layer 3 — `/api/airplane` endpoint

`tests/dashboard/api/airplane-route.test.ts` *(new)*: POST `{ action: "on" | "off" }` invokes the right MCP tool; 400 on malformed action; idempotency.

### Layer 4 — UI components

`tests/dashboard/components/AirplanePill.test.tsx` *(new)*: snapshot tests for the four visual states (off / on-ready / on-not-ready / on-unsupported), driven by mocked `useMcpQuery`.

`tests/dashboard/components/ChatHeader-airplane-chip.test.tsx` *(new)*: chip mirrors the pill via shared cache key; tooltip surfaces configured model name.

`tests/dashboard/features/hooks/useCliChat-airplane-transitions.test.ts` *(new)*: transition system message appended **before** stopCli when airplane changes during a running session; 409 `setup_hint` surfaces as monospaced inline system message.

### Layer 5 — Settings → Security

`tests/dashboard/settings/SecurityTab-local-backend.test.tsx` *(new)*: "Local backend" subsection renders detected ollama path, model dropdown populated from the same `get-local-backend-status` query (no separate `list-ollama-models` tool), "Test connection" button shows pass/fail badge inline; selecting a model calls `update-preference`; agent compatibility matrix lists Ollama integrations with green checks for supported and tooltips for unsupported.

### Layer 6 — End-to-end smoke (gated by env var)

`tests/e2e/airplane-mode.spec.ts` *(new, Playwright or equivalent)*. Two scenarios:

- **Happy path:** Ollama running with model pulled. Flip pill on → start claude → first message round-trips through local model. Chip shows model name.
- **Setup-needed path:** Ollama stopped. Flip pill on → start claude → 409 `setup_hint` rendered in chat.

Skipped on CI when `AUGUR_E2E_OLLAMA=1` is not set. CI matrix can pin macOS-only initially without losing Windows coverage from unit-level platform-parametrized tests.

### Discipline

- All new tests are real — no `pytest.mark.skip`, no eslint-disable, no mocked test passing for broken behavior (project rule 5).
- Subprocess and `mcpCall` are mocked at unit level; the real Ollama is exercised once in the smoke test.
- The smoke test gate is opt-in (env var), not skip-by-default.

## Out of scope (explicit)

- Auto-detect connectivity watchdog (`connectivity.py` keeps existing tests; not wired into UI).
- Per-agent model override (single shared model in v1).
- Non-Ollama backends (vLLM, LM Studio) — `ollama launch` keeps the door open: if those backends ship integrations Ollama recognizes, this design covers them; otherwise they get a separate spec.
- Auto-fallback to cloud when local is unhealthy (explicitly rejected).
- Gemini support — Gemini CLI is not in Ollama's integration list and lacks a generic OpenAI-compatible endpoint flag. Marked `unsupported` with clear UI affordance. A future spec can add a Gemini-via-proxy path if needed.
- Cursor CLI / Copilot CLI: copilot-cli **is** supported via `ollama launch copilot`; cursor-cli is not in the integration list and stays unsupported.

## Risks

- **Hard dependency on Ollama ≥ 0.21** for the `launch` subcommand. Older installs return `unknown command`; we surface that as `binary_missing` with a "reinstall/upgrade" hint. Acceptable: `launch` is a flagship Ollama feature, not a deprecated corner.
- **Local model quality** — A small local model (e.g. qwen3.5 9B) will struggle with complex multi-step skills and long prompts. Known limitation; not a v1 problem to solve. Users who want better local performance pull a bigger model via the Settings → Security dropdown.
- **Memory loss across airplane toggles mid-session** — explicit, surfaced via the transition system message. Re-implementing cross-process conversational memory is out of scope for v1.

## References

- Existing partial design: `docs/superpowers/specs/2026-03-28-local-mode-ollama-design.md`
- Existing partial plan: `docs/superpowers/plans/2026-03-28-local-mode-ollama.md`
- Codex `--oss` flag: https://developers.openai.com/codex/config-advanced
- OpenCode Ollama provider config: https://github.com/anomalyco/opencode/blob/dev/packages/web/src/content/docs/providers.mdx
- Gemini CLI configuration reference: https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md
- Ollama 0.21.1 `launch` subcommand: verified against local install, integration list (claude, cline, codex, copilot, droid, hermes, kimi, opencode, openclaw, pi, vscode).
