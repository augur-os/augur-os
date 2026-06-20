---
status: Implemented
date: 2026-05-05
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-603: Airplane Mode UX and Local-Backend Routing

## Context

Augur's airplane mode was cosmetic at the routing level: the existing `toggle-airplane-mode` MCP tool, `/airplane` slash command, and SecurityTab toggle only stripped auto-approve flags from spawned CLIs — they did not change which backend the agent talked to. The toggle lived only in **Settings → Security**, far from where users work, and the chat UI gave no signal whether the running agent was using a cloud or local model. A localStorage `airplaneModeStore` produced persistent client/server desync.

Three coordinated changes close those gaps: surface the toggle globally (top-bar pill plus a mirror chip in the chat header) so it is reachable from anywhere; show in-chat transitions with a single inline system message when airplane state flips mid-session; and wire the toggle to actually change agent routing by spawning supported agents through `ollama launch <agent>`, deferring per-agent integration knowledge to Ollama instead of maintaining a hand-rolled strategy table in Augur.

The single source of truth is `preferences.yaml` (airplane state plus `local_backends.ollama` model). The browser store is replaced by a thin selector around `useMcpQuery` against `get-local-backend-status`, with a single shared cache key (`"airplane-status"`) so pill, chip, and SecurityTab re-render in lockstep when one consumer invalidates.

Primary platform target is Windows + macOS (Ollama runs primarily on Windows for end users). The CLI start path performs a pre-flight check via a new MCP tool `get-airplane-launch-overrides`; it returns either a ready argv (`["ollama","launch",cliId,"--model",model,"--", ...]`) or a 409 with a platform-aware `setup_hint`.

## Decision

Implement airplane mode end-to-end with the following design choices:

1. **Toggle placement** — global top-bar pill (canonical) plus a mirror chip in the chat header. Settings → Security keeps deep config (model dropdown, agent compatibility matrix, test connection) but is no longer the only flip point.
2. **In-chat visibility** — header chip plus an inline transition system message when airplane state flips during a running session. No per-message tags.
3. **Launch mechanism** — defer to `ollama launch <agent>` for any agent in Ollama's integration list (claude, cline, codex, copilot, droid, hermes, kimi, opencode, openclaw, pi, vscode). Zero per-agent maintenance for Augur.
4. **Manual toggle only** — no auto-detect connectivity watchdog in v1. Manual flip is unambiguous in the UI chip.
5. **Soft toggle + pre-flight at spawn** — the toggle always flips; agent spawn returns 409 with `setup_hint` when Ollama isn't ready (binary missing, server not running, model missing, agent unsupported, version too old).
6. **Single shared local LLM** — `local_backends.ollama.model` is one model for all supported agents in v1.
7. **State invariants** — `preferences.yaml` is canonical; the browser never writes localStorage for airplane state; `["get-local-backend-status"]` is the shared cache key; CLI restart on toggle is a derived effect, not a primary action.

New surfaces: `AirplanePill.tsx` (global pill, four visual states), `/api/airplane` POST endpoint, `get-airplane-launch-overrides` MCP tool, platform-aware Ollama binary detection, ChatHeader chip, expanded SecurityTab with model dropdown and agent compatibility matrix. Refactored: `airplaneModeStore.ts` replaced by an MCP-query hook; `/api/cli` start path consults pre-flight before spawning; `useCliChat` emits transition system messages and surfaces 409 setup hints inline.

## Consequences

### Positive
- Toggle is reachable from anywhere; running agent's backend is unambiguous.
- Single source of truth eliminates the long-standing client/server desync.
- Zero per-agent maintenance — Ollama owns codex `--oss`, opencode `opencode.json`, claude env vars, etc.
- Failure surfaces at the right boundary (agent spawn) with platform-aware hints rather than silent fallback.
- Toggling is atomic; CLI restart is a derived effect, keeping the action predictable.

### Negative
- Hard dependency on Ollama ≥ 0.21 for the `launch` subcommand. Older installs surface as `binary_missing`.
- Local model quality (e.g. qwen3.5 9B) will struggle with complex multi-step skills — known limitation, mitigated by allowing model swap via Settings.
- Agent loses conversational memory across an airplane-toggle restart; transition system message implicitly cues the user.
- Gemini CLI lacks Ollama integration and a generic OpenAI-compatible flag — marked `unsupported`.

### Neutral
- `connectivity.py` watchdog code remains unused for now; explicitly deferred.
- Detached sessions stay on whichever backend they started on until reconnected.
- Shell-style `setup_hint` strings rendered monospaced with copy button — minor UI investment.

## Alternatives Considered

### Alternative 1: Per-agent strategy table in Augur (`local_backends.yaml` env/flags/config_file dispatcher)
Rejected. Maintaining per-agent quirks (codex `--oss`, opencode provider config, claude env vars) duplicates Ollama's integration knowledge and creates ongoing maintenance debt. `ollama launch` is a flagship Ollama feature.

### Alternative 2: Auto-detect connectivity watchdog (auto-flip airplane on/off)
Deferred. "Forced" vs "auto-flipped" semantics create UI ambiguity in the chip. Manual toggle is unambiguous; the watchdog code stays unused for v1.

### Alternative 3: Auto-fallback to cloud when local is unhealthy
Explicitly rejected. Would silently leak data the user wanted kept local — a violation of user intent.

### Alternative 4: Per-agent model overrides
Out of scope for v1. Single shared model matches the user's stated simplification; can be extended later without re-architecting.

## References
- Plan: docs/superpowers/plans/2026-05-05-airplane-mode-ux.md
- Spec: docs/superpowers/specs/2026-05-05-airplane-mode-ux-design.md
- Supersedes (in part): docs/superpowers/specs/2026-03-28-local-mode-ollama-design.md
