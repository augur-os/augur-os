---
status: Implemented
date: '2026-02-02'
deciders: []
related: []
hub: null
tags:
- cli
- based
- chat
- window
- file
superseded_by: null
---

# ADR-034: CLI-Based Chat Window with File Attachment Support

## Context

The Augur dashboard currently has a `FloatingChat` component (`src/dashboard/components/FloatingChat.tsx`) that provides a simple chat overlay with four modes: `ide`, `remote`, `local`, and `auto`. However, this chat window has significant limitations:

1. **No real CLI integration** — The chat simulates responses with `setTimeout` (line 132). Messages are never actually sent to any CLI process. The `TerminalTab` (`plugins/ai/skills/ai_bridge/augur/tabs/TerminalTab.tsx`) executes augur-specific commands via `/api/tools/terminal` but is a separate, disconnected experience from the chat.

2. **No CLI selection** — Augur supports 7+ CLI agents (Claude Code, Codex, Cursor CLI, Kimi, Gemini, OpenCode, claude-kimi) defined in `mprocs.yaml` and registered in the adapter registry (`plugins/ai/skills/ai_bridge/augur/registry.py`). Users cannot choose which CLI to interact with from the chat.

3. **No file attachment** — CLI agents support file references in their prompts but the dashboard has no mechanism for users to attach files (drag-and-drop or button). Users must manually type file paths.

4. **No process persistence** — When the chat is minimized/closed, there is no persistent CLI subprocess. Each interaction is stateless. The `mprocs.yaml` configuration shows the desired process model (long-running CLI sessions per agent) but this isn't exposed in the dashboard.

### What exists today

| Component | Location | Role |
|-----------|----------|------|
| FloatingChat | `src/dashboard/components/FloatingChat.tsx` | Simulated chat UI, no real backend |
| chatStore | `src/dashboard/lib/stores/chatStore.ts` | Zustand store: `isOpen`, `mode`, `agent`, `isWaiting` |
| actionModalStore | `src/dashboard/lib/stores/actionModalStore.ts` | Action execution state, agent selection |
| TerminalTab | `plugins/ai/skills/ai_bridge/augur/tabs/TerminalTab.tsx` | Augur CLI terminal (augur/exo commands only) |
| Terminal API | `src/dashboard/app/api/tools/terminal/route.ts` | Stateless command execution, whitelisted |
| CliAgentAdapter | `plugins/ai/skills/ai_bridge/augur/cli_agent_base.py` | Base class for CLI agents |
| Adapter Registry | `plugins/ai/skills/ai_bridge/augur/registry.py` | Registers all CLI adapters |
| mprocs.yaml | `mprocs.yaml` | CLI process launch configs |

## Decision

### Component 1: CLI Chat Store (Extended State)

Extended `chatStore.ts` with CLI-specific state: `CliId`, `AttachedFile`, `CliProcessState`, plus actions for selecting CLIs, managing process state, and file attachment CRUD.

### Component 2: CLI Process Manager API

New API routes under `/api/cli/`:
- `POST /api/cli` with `action: start|send|stop` — Manages long-running CLI subprocesses via `child_process.spawn`
- `GET /api/cli?cliId=xxx` — Process status
- `GET /api/cli?cliId=xxx&stream=true` — SSE output stream

### Component 3: File Upload & Staging API

`POST /api/cli/upload` — Accepts multipart file uploads, stores in `runtime/cli-uploads/` with timestamp prefix. 50MB limit. Auto-cleans files older than 24h.

### Component 4: Enhanced FloatingChat UI

Replaced `FloatingChat.tsx` with CLI-aware chat panel: CLI selector dropdown, file attachment button, drag-and-drop, minimized pill state.

### Component 5: CLI Configuration Resolver

Python utility (`resolve_cli_config.py`) and API route (`/api/cli/configs`) to read `mprocs.yaml` and expose CLI configurations to the dashboard.

### Directory Structure

```
src/dashboard/
├── app/api/cli/
│   ├── route.ts              # CLI process management
│   ├── upload/
│   │   └── route.ts          # File upload to staging
│   └── configs/
│       └── route.ts          # CLI configuration list
├── components/
│   └── FloatingChat.tsx      # Enhanced (replaced)
├── hooks/
│   └── useCliChat.ts         # Hook: process lifecycle, message streaming, file handling
└── lib/stores/
    └── chatStore.ts          # Extended with CLI state

plugins/ai/skills/ai_bridge/
├── scripts/
│   └── resolve_cli_config.py # mprocs.yaml parser

runtime/
└── cli-uploads/              # Staging directory (gitignored, ephemeral)
```

## Testing & Verification

### Unit Tests

| Test | Expected Result | Status |
|------|-----------------|--------|
| test_cli_store_select_cli | Updates selectedCli | PASS |
| test_cli_store_add_attached_file | Appends to attachedFiles | PASS |
| test_cli_store_remove_attached_file | Removes by stagedPath | PASS |
| test_cli_store_clear_attached_files | Empties array | PASS |
| test_cli_start_spawns_process | Returns running + pid | PASS |
| test_cli_start_invalid_cli_rejects | Returns 400 | PASS |
| test_cli_send_writes_to_stdin | Writes to process stdin | PASS |
| test_cli_send_without_process_errors | Returns 409 | PASS |
| test_cli_stop_terminates_process | SIGTERM + exited | PASS |
| test_cli_status_returns_running | Running with pid/uptime | PASS |
| test_cli_status_returns_idle | Idle when not started | PASS |
| test_upload_stores_file_in_staging | Writes to cli-uploads/ | PASS |
| test_upload_returns_staged_path | Absolute path with cli-uploads | PASS |
| test_upload_rejects_oversized_file | Returns 413 | PASS |
| test_upload_rejects_no_file | Returns 400 | PASS |
| test_resolve_cli_config_reads_mprocs | Returns matching entries | PASS |
| test_resolve_cli_config_missing_file | Raises FileNotFoundError | PASS |
| test_message_includes_file_path | File path in stdin | PASS |
| test_switch_cli_stops_previous | SIGTERM on old + start new | PASS |
| test_minimize_keeps_process_alive | No kill called | PASS |
| test_cleanup_removes_old_uploads | Unlinks old files | PASS |

## Consequences

### Positive
- Users interact with any CLI agent from a single, persistent chat interface
- File attachment eliminates manual path typing
- CLI process persistence means context is maintained across page navigation
- Leverages existing `mprocs.yaml` configuration
- Runtime staging directory is gitignored and auto-cleaned

### Negative
- Long-running CLI processes consume system resources
- SSE streaming adds complexity to error handling
- File upload staging directory needs cleanup logic
- Switching CLIs discards the running conversation

### Migration
- `FloatingChat.tsx` — Rewritten; old simulated chat logic removed
- `chatStore.ts` — Extended with new fields; existing fields preserved
- `runtime/` — New `cli-uploads/` subdirectory (already gitignored)
- No existing API routes modified — only new routes added under `/api/cli/`
