---
description: Toggle airplane mode and inspect local backend readiness
visibility: core
---

# /airplane

Toggle airplane mode to route agent work through the local Ollama backend instead
of cloud APIs.

## Usage

- `/airplane on` — force airplane mode on
- `/airplane off` — disable airplane mode
- `/airplane status` — show current state and backend readiness
- `/airplane` — toggle the current state

## Execution

### `on`

1. Call `toggle-airplane-mode` with `{ "action": "on" }`
2. Call `get-local-backend-status` with `{}`
3. If Ollama is ready, report the selected model and launch command
4. If Ollama is not ready, show the missing installation/server/model guidance

### `off`

1. Call `toggle-airplane-mode` with `{ "action": "off" }`
2. Report that cloud routing and auto-detect are re-enabled

### `status`

1. Call `toggle-airplane-mode` with `{ "action": "status" }`
2. Call `get-local-backend-status` with `{}`
3. Present airplane mode, connectivity, Ollama install state, server state, model, and launch command

### Toggle

1. Call `toggle-airplane-mode` with `{ "action": "toggle" }`
2. Report the new state using the same format as `on` or `off`

## Global Flags

- `--help` — show usage and stop
- `--evolve` — emit execution telemetry after running

## Examples

- `/airplane on`
- `/airplane off`
- `/airplane status`

